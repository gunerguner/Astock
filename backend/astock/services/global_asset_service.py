"""全球资产价格水位：历史最高点刷新与页面查询。"""

import logging
from datetime import date

from sqlmodel import Session, select

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS
from astock.core.datetime_utils import iso_now, now_local, synced_today
from astock.core.redis_client import (
    LATEST_TRADING_DATE_KEY,
    get_json,
    get_string,
    price_key,
    recent_closes_key,
    set_json,
    set_string,
)
from astock.core.sync_status import SyncStatus
from astock.core.exceptions import AppError
from astock.models.asset_high import AssetHigh
from astock.schemas.analysis import PriceLevelItem, PriceLevelPendingItem, PriceLevelsResponse
from astock.services.price_utils import (
    baseline_prices,
    latest_trading_date,
    pct_change,
    read_recent_closes_cache,
    sorted_dates,
    write_recent_closes_cache,
)
from astock.services.sync_store import batch_upsert, get_sync_meta, upsert_sync_meta
from astock.sources.akshare_client import fetch_all_assets

logger = logging.getLogger(__name__)

_CONCLUSIONS = [(5, "接近历史高点"), (20, "适度回调"), (50, "显著回调")]


def _conclusion(percentage_diff: float) -> str:
    abs_diff = abs(percentage_diff)
    for threshold, label in _CONCLUSIONS:
        if abs_diff < threshold:
            return label
    return "深度回调"


def _write_price_cache(ticker: str, closes: dict[str, float]) -> None:
    if not closes:
        return
    sorted_items = sorted(closes.items())
    for d, price in sorted_items:
        set_string(price_key(ticker, d), str(price), ttl=ASSET_PRICE_CACHE_TTL)
    write_recent_closes_cache(
        set_json,
        recent_closes_key(ticker),
        closes,
        ttl=ASSET_PRICE_CACHE_TTL,
    )


def _read_price_cache(ticker: str) -> dict[str, float]:
    closes = read_recent_closes_cache(get_json, recent_closes_key(ticker))
    if closes:
        return closes

    latest = get_string(LATEST_TRADING_DATE_KEY)
    if latest:
        raw = get_string(price_key(ticker, latest))
        if raw is not None:
            return {latest: float(raw)}
    return {}


def _backfill_from_akshare(
    assets: list[dict[str, str]],
) -> tuple[dict[str, dict[str, float]], list[str]]:
    errors: list[str] = []
    all_closes: dict[str, dict[str, float]] = {}
    fetch_results = fetch_all_assets(assets)
    for asset in assets:
        ticker = asset["ticker"]
        result = fetch_results.get(ticker)
        if result is None or not result.ok or not result.records:
            if result:
                errors.extend(result.errors)
            else:
                errors.append(f"{ticker}: 未返回数据")
            continue
        record = result.records[0]
        closes = record.get("recent_closes") or {}
        if not closes:
            errors.append(f"{ticker}: 最近收盘价为空")
            continue
        all_closes[ticker] = closes
        _write_price_cache(ticker, closes)
    latest = latest_trading_date(all_closes)
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return all_closes, errors


def refresh_asset_highs(db: Session) -> dict:
    meta = get_sync_meta(db, "asset_high")
    if (
        meta
        and meta.last_status == SyncStatus.SUCCESS
        and synced_today(meta.last_synced_at)
    ):
        total = len(db.exec(select(AssetHigh)).all())
        if total > 0:
            logger.info(
                "全球资产最高点刷新跳过: 今日已成功同步 (last_synced_at=%s)",
                meta.last_synced_at,
            )
            return {
                "imported": 0,
                "total": total,
                "last_date": meta.last_synced_date,
                "last_synced_at": meta.last_synced_at,
                "status": SyncStatus.SUCCESS,
                "source_errors": {"global_assets": None},
            }

    cached_at = iso_now()
    records: list[dict] = []
    errors: list[str] = []
    all_closes_for_latest: dict[str, dict[str, float]] = {}

    fetch_results = fetch_all_assets()
    for asset in GLOBAL_ASSETS:
        ticker = asset["ticker"]
        if asset.get("data_pending"):
            continue
        result = fetch_results.get(ticker)
        if result is None or not result.ok or not result.records:
            if result:
                errors.extend(result.errors)
            else:
                errors.append(f"{ticker}: 未返回数据")
            continue

        record = result.records[0]
        try:
            all_time_high = float(record["all_time_high"])
            ath_date = str(record["ath_date"])
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{ticker}: 历史最高点数据无效 ({e})")
            continue
        closes = record.get("recent_closes") or {}
        _write_price_cache(ticker, closes)
        all_closes_for_latest[ticker] = closes

        records.append(
            {
                "ticker": ticker,
                "name": asset["name"],
                "asset_type": asset["asset_type"],
                "all_time_high": all_time_high,
                "ath_date": ath_date,
                "cached_at": cached_at,
            }
        )

    imported = (
        batch_upsert(db, AssetHigh, records, ["ticker"], commit_mode="single")
        if records
        else 0
    )
    latest = latest_trading_date(all_closes_for_latest)
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)

    if not errors:
        status = SyncStatus.SUCCESS
    elif imported:
        status = SyncStatus.PARTIAL_FAILURE
    else:
        status = SyncStatus.FAILED

    last_synced_at = upsert_sync_meta(
        db,
        "asset_high",
        last_synced_date=latest,
        status=status,
        error="; ".join(errors[:5]) if errors else None,
    )

    return {
        "imported": imported,
        "total": len(records),
        "last_date": latest,
        "last_synced_at": last_synced_at,
        "status": status,
        "source_errors": {"global_assets": "; ".join(errors[:5]) if errors else None},
    }


def _ensure_price_cache(
    assets: list[dict[str, str]], *, force_refresh: bool = False
) -> tuple[dict[str, dict[str, float]], list[str]]:
    if not force_refresh:
        all_closes: dict[str, dict[str, float]] = {}
        missing: list[dict[str, str]] = []
        for asset in assets:
            ticker = asset["ticker"]
            closes = _read_price_cache(ticker)
            if closes:
                all_closes[ticker] = closes
            else:
                missing.append(asset)
        if not missing:
            latest = get_string(LATEST_TRADING_DATE_KEY)
            if latest is None:
                latest = latest_trading_date(all_closes)
                if latest:
                    set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
            return all_closes, []
        backfill, errors = _backfill_from_akshare(missing)
        all_closes.update(backfill)
        return all_closes, errors

    return _backfill_from_akshare(assets)


def _pending_item(asset: dict[str, str]) -> PriceLevelPendingItem:
    return PriceLevelPendingItem(
        ticker=asset["ticker"],
        name=asset["name"],
        asset_type=asset["asset_type"],
        conclusion="待接入",
    )


def get_price_levels(db: Session, *, force_refresh: bool = False) -> PriceLevelsResponse:
    rows = db.exec(select(AssetHigh)).all()
    if not rows and not force_refresh:
        meta = get_sync_meta(db, "asset_high")
        if meta is None:
            raise ValueError("全球资产历史最高点数据为空，请先刷新数据")

    all_closes, cache_errors = _ensure_price_cache(GLOBAL_ASSETS, force_refresh=force_refresh)

    row_map = {row.ticker: row for row in rows}
    items: list[PriceLevelItem | PriceLevelPendingItem] = []
    now = now_local()
    as_of = iso_now()

    for asset in GLOBAL_ASSETS:
        ticker = asset["ticker"]
        closes = all_closes.get(ticker, {})
        current, prev_close, week_ago_close = baseline_prices(closes)
        if current is None:
            if asset.get("data_pending"):
                items.append(_pending_item(asset))
            else:
                cache_errors.append(f"{ticker}: 当前价格缺失")
            continue

        row = row_map.get(ticker)
        if row is None:
            cache_errors.append(f"{ticker}: 数据库无 ATH 记录，请先刷新导入")
            continue

        all_time_high = float(row.all_time_high)
        ath_date = row.ath_date
        if current > all_time_high:
            all_time_high = current
            ath_date = sorted_dates(closes)[-1] if closes else ath_date

        percentage_diff = (current - all_time_high) / all_time_high * 100
        try:
            ath_days = (now.date() - date.fromisoformat(ath_date)).days
        except ValueError:
            ath_days = 0

        items.append(
            PriceLevelItem(
                ticker=ticker,
                name=row.name,
                asset_type=row.asset_type,
                current_price=round(current, 4),
                all_time_high=round(all_time_high, 4),
                ath_date=ath_date,
                percentage_diff=round(percentage_diff, 2),
                ath_days=ath_days,
                daily_change=round(v, 2)
                if (v := pct_change(current, prev_close)) is not None
                else None,
                weekly_change=round(v, 2)
                if (v := pct_change(current, week_ago_close)) is not None
                else None,
                conclusion=_conclusion(percentage_diff),
            )
        )

    items.sort(
        key=lambda x: (
            0 if isinstance(x, PriceLevelPendingItem) else 1,
            x.percentage_diff if isinstance(x, PriceLevelItem) else 0,
        )
    )

    meta = get_sync_meta(db, "asset_high")
    latest_trading_date_value = get_string(LATEST_TRADING_DATE_KEY) or (
        meta.last_synced_date if meta else None
    )
    if latest_trading_date_value is None:
        raise AppError("无法确定最新交易日，请先刷新全球资产数据")

    return PriceLevelsResponse(
        last_synced_at=meta.last_synced_at if meta else None,
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        items=items,
        cache_errors=cache_errors[:5] if cache_errors else None,
    )
