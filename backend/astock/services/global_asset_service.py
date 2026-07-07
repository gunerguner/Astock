"""全球资产价格水位：历史最高点刷新与页面查询。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlmodel import Session, select

from astock.config import (
    ASSET_PRICE_CACHE_TTL,
    GLOBAL_ASSET_RECENT_DAYS,
    GLOBAL_ASSETS,
)
from astock.core.redis_client import (
    LATEST_TRADING_DATE_KEY,
    get_json,
    get_string,
    price_key,
    recent_closes_key,
    set_json,
    set_string,
)
from astock.models.asset_high import AssetHigh
from astock.sources.akshare_client import (
    extract_ath,
    extract_recent_closes,
    fetch_all_assets,
    fetch_asset_history,
)

logger = logging.getLogger(__name__)

_CONCLUSIONS = [(5, "接近历史高点"), (20, "适度回调"), (50, "显著回调")]


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pct_change(cur: float, base: float | None) -> float | None:
    if base and base > 0:
        return (cur - base) / base * 100
    return None


def _conclusion(percentage_diff: float) -> str:
    abs_diff = abs(percentage_diff)
    for threshold, label in _CONCLUSIONS:
        if abs_diff < threshold:
            return label
    return "深度回调"


def _sorted_dates(closes: dict[str, float]) -> list[str]:
    return sorted(closes.keys())


def _write_price_cache(ticker: str, closes: dict[str, float]) -> None:
    if not closes:
        return
    sorted_items = sorted(closes.items())
    for d, price in sorted_items:
        set_string(price_key(ticker, d), str(price), ttl=ASSET_PRICE_CACHE_TTL)
    set_json(
        recent_closes_key(ticker),
        [{"date": d, "close": price} for d, price in sorted_items],
        ttl=ASSET_PRICE_CACHE_TTL,
    )


def _read_price_cache(ticker: str) -> dict[str, float]:
    cached = get_json(recent_closes_key(ticker))
    if isinstance(cached, list):
        closes: dict[str, float] = {}
        for item in cached:
            if not isinstance(item, dict):
                continue
            d = item.get("date")
            close = item.get("close")
            if d and close is not None:
                closes[str(d)] = float(close)
        if closes:
            return closes

    latest = get_string(LATEST_TRADING_DATE_KEY)
    if latest:
        raw = get_string(price_key(ticker, latest))
        if raw is not None:
            return {latest: float(raw)}
    return {}


def _latest_global_trading_date(all_closes: dict[str, dict[str, float]]) -> str | None:
    dates: set[str] = set()
    for closes in all_closes.values():
        dates.update(closes.keys())
    return max(dates) if dates else None


def _baseline_prices(closes: dict[str, float]) -> tuple[float | None, float | None, float | None]:
    """返回 (当前价, 昨收基准, 约5个交易日前基准)。"""
    dates = _sorted_dates(closes)
    if not dates:
        return None, None, None
    current = closes[dates[-1]]
    prev = closes[dates[-2]] if len(dates) >= 2 else None
    week_ago = closes[dates[-6]] if len(dates) >= 6 else None
    return current, prev, week_ago


def _synced_today(last_synced_at: str | None) -> bool:
    if not last_synced_at:
        return False
    try:
        return datetime.fromisoformat(last_synced_at).date() == date.today()
    except ValueError:
        return False


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
    latest = _latest_global_trading_date(all_closes)
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return all_closes, errors


def refresh_asset_highs(db: Session) -> dict[str, Any]:
    from astock.services.import_service import _batch_upsert, get_sync_meta, upsert_sync_meta

    meta = get_sync_meta(db, "asset_high")
    if (
        meta
        and meta.last_status == "success"
        and _synced_today(meta.last_synced_at)
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
                "status": "success",
                "source_errors": {"global_assets": None},
            }

    cached_at = _iso_now()
    records: list[dict[str, Any]] = []
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
        all_time_high = float(record["all_time_high"])
        ath_date = str(record["ath_date"])
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

    imported = _batch_upsert(db, AssetHigh, records, ["ticker"]) if records else 0
    latest = _latest_global_trading_date(all_closes_for_latest)
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)

    status = "success" if not errors else ("partial_failure" if imported else "failed")
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
                latest = _latest_global_trading_date(all_closes)
                if latest:
                    set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
            return all_closes, []
        backfill, errors = _backfill_from_akshare(missing)
        all_closes.update(backfill)
        return all_closes, errors

    return _backfill_from_akshare(assets)


def _pending_item(asset: dict[str, str]) -> dict[str, Any]:
    return {
        "ticker": asset["ticker"],
        "name": asset["name"],
        "asset_type": asset["asset_type"],
        "current_price": None,
        "all_time_high": None,
        "ath_date": None,
        "percentage_diff": None,
        "ath_days": None,
        "daily_change": None,
        "weekly_change": None,
        "conclusion": "待接入",
        "data_pending": True,
    }


def get_price_levels(db: Session, *, force_refresh: bool = False) -> dict[str, Any]:
    from astock.services.import_service import get_sync_meta

    rows = db.exec(select(AssetHigh)).all()
    if not rows and not force_refresh:
        meta = get_sync_meta(db, "asset_high")
        if meta is None:
            raise ValueError("全球资产历史最高点数据为空，请先刷新数据")

    all_closes, cache_errors = _ensure_price_cache(GLOBAL_ASSETS, force_refresh=force_refresh)

    row_map = {row.ticker: row for row in rows}
    items: list[dict[str, Any]] = []
    now = datetime.now()
    as_of = _iso_now()

    for asset in GLOBAL_ASSETS:
        ticker = asset["ticker"]
        closes = all_closes.get(ticker, {})
        current, prev_close, week_ago_close = _baseline_prices(closes)
        if current is None:
            if asset.get("data_pending"):
                items.append(_pending_item(asset))
            continue

        row = row_map.get(ticker)
        if row is None:
            try:
                df = fetch_asset_history(ticker, asset["asset_type"])
                ath = extract_ath(df)
                if ath is None:
                    continue
                all_time_high, ath_date = ath
                closes_from_hist = extract_recent_closes(df, GLOBAL_ASSET_RECENT_DAYS)
                _write_price_cache(ticker, closes_from_hist)
                row = AssetHigh(
                    ticker=ticker,
                    name=asset["name"],
                    asset_type=asset["asset_type"],
                    all_time_high=all_time_high,
                    ath_date=ath_date,
                    cached_at=as_of,
                )
                db.merge(row)
                db.commit()
                row_map[ticker] = row
                current, prev_close, week_ago_close = _baseline_prices(
                    closes_from_hist or closes
                )
                if current is None:
                    continue
            except Exception as e:
                logger.warning("懒加载 %s ATH 失败: %s", ticker, e)
                continue

        all_time_high = float(row.all_time_high)
        ath_date = row.ath_date
        if current > all_time_high:
            all_time_high = current
            ath_date = _sorted_dates(closes)[-1] if closes else ath_date
            row.all_time_high = all_time_high
            row.ath_date = ath_date
            row.cached_at = as_of
            db.merge(row)
            db.commit()

        percentage_diff = (current - all_time_high) / all_time_high * 100
        try:
            ath_days = (now.date() - date.fromisoformat(ath_date)).days
        except ValueError:
            ath_days = 0

        items.append(
            {
                "ticker": ticker,
                "name": row.name,
                "asset_type": row.asset_type,
                "current_price": round(current, 4),
                "all_time_high": round(all_time_high, 4),
                "ath_date": ath_date,
                "percentage_diff": round(percentage_diff, 2),
                "ath_days": ath_days,
                "daily_change": round(v, 2)
                if (v := _pct_change(current, prev_close)) is not None
                else None,
                "weekly_change": round(v, 2)
                if (v := _pct_change(current, week_ago_close)) is not None
                else None,
                "conclusion": _conclusion(percentage_diff),
            }
        )

    items.sort(
        key=lambda x: (
            0 if x.get("data_pending") else 1,
            x["percentage_diff"] if x["percentage_diff"] is not None else 0,
        )
    )

    meta = get_sync_meta(db, "asset_high")
    latest_trading_date = get_string(LATEST_TRADING_DATE_KEY) or (
        meta.last_synced_date if meta else None
    )

    return {
        "last_synced_at": meta.last_synced_at if meta else None,
        "as_of": as_of,
        "latest_trading_date": latest_trading_date,
        "items": items,
        "cache_errors": cache_errors[:5] if cache_errors else None,
    }
