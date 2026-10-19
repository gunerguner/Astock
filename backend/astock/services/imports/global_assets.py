"""全球资产历史最高点刷新（写路径）。"""

import logging
import time

from sqlmodel import Session, select

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS, GlobalAssetConfig
from astock.core.datetime_utils import is_multi_market_synced, iso_now, market_for_asset_type
from astock.core.price_utils import anchor_date_excluding_today, closes_cover_settled
from astock.core.sync_status import SyncStatus
from astock.datasets.global_assets import fetch_all_assets
from astock.models.asset_high import AssetHigh
from astock.services.cache.asset_prices import (
    global_asset_markets,
    parse_asset_fetch_results,
    read_price_cache,
    write_price_cache,
)
from astock.services.cache.closes import cache_latest_trading_date
from astock.services.cache.keys import LATEST_TRADING_DATE_KEY
from astock.services.sync.results import (
    ImportResult,
    build_result,
    finalize_import_result,
    resolve_status,
)
from astock.services.sync.store import batch_upsert, count_rows, get_sync_meta, upsert_sync_meta
from astock.services.sync.watermark import forward_date

logger = logging.getLogger(__name__)


def should_skip_asset_highs(db: Session):
    """水位已覆盖中美结算日且表非空时可跳过；返回 (是否跳过, sync_meta)。"""
    meta = get_sync_meta(db, "asset_high")
    if not (
        meta
        and meta.last_status == SyncStatus.SUCCESS
        and is_multi_market_synced(meta.last_synced_date)
    ):
        return False, meta
    if count_rows(db, AssetHigh) <= 0:
        return False, meta
    return True, meta


def persist_higher_close(
    db: Session,
    *,
    ticker: str,
    name: str,
    asset_type: str,
    price: float,
    price_date: str,
) -> tuple[float, str]:
    """现价高于已存 ATH 时写回，返回应展示的最高价和日期。"""
    row = db.exec(select(AssetHigh).where(AssetHigh.ticker == ticker)).first()
    if row is not None and price <= float(row.all_time_high):
        return float(row.all_time_high), row.ath_date
    batch_upsert(
        db,
        AssetHigh,
        [
            {
                "ticker": ticker,
                "name": name or (row.name if row else ticker),
                "asset_type": asset_type or (row.asset_type if row else "stock"),
                "all_time_high": price,
                "ath_date": price_date,
                "cached_at": iso_now(),
            }
        ],
        ["ticker"],
    )
    return price, price_date


def _needs_asset_fetch(db: Session, asset: GlobalAssetConfig) -> bool:
    """无 ATH 或近期收盘未覆盖结算日时才打外网。待接入资产不拉取。"""
    if asset.get("data_pending"):
        return False
    ticker = asset["ticker"]
    row = db.exec(select(AssetHigh).where(AssetHigh.ticker == ticker)).first()
    if row is None:
        return True
    market = market_for_asset_type(asset["asset_type"])
    closes = read_price_cache(ticker, market=market)
    return not closes_cover_settled(closes, market)


def refresh_asset_highs(db: Session) -> ImportResult:
    """刷新全球资产历史最高点入库，并同步价格缓存与最新交易日。"""
    start_ts = time.perf_counter()
    skip, meta = should_skip_asset_highs(db)
    if skip:
        if meta is None:
            raise RuntimeError("asset_high: should_skip 为真但 sync_meta 缺失")
        total = count_rows(db, AssetHigh)
        logger.info(
            "全球资产最高点刷新跳过: 已覆盖最近可结算日 (last_synced_date=%s)",
            meta.last_synced_date,
        )
        return build_result(
            imported=0,
            total=total,
            last_date=meta.last_synced_date,
            ok=True,
            source_errors={},
            last_synced_at=meta.last_synced_at,
            elapsed=round(time.perf_counter() - start_ts, 2),
        )

    cached_at = iso_now()
    records: list[dict] = []
    all_closes_for_latest: dict[str, dict[str, float]] = {}
    old_meta = get_sync_meta(db, "asset_high")
    old_date = old_meta.last_synced_date if old_meta else None

    to_fetch = [asset for asset in GLOBAL_ASSETS if _needs_asset_fetch(db, asset)]
    fetch_results = fetch_all_assets(to_fetch) if to_fetch else {}
    parsed, errors = parse_asset_fetch_results(
        to_fetch, fetch_results, skip_pending=True
    )
    for row in parsed:
        ticker = row.asset["ticker"]
        record = row.record
        market = row.market
        closes = row.closes
        try:
            all_time_high = float(record["all_time_high"])
            ath_date = str(record["ath_date"])
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{ticker}: 历史最高点数据无效 ({e})")
            continue
        existing = db.exec(select(AssetHigh).where(AssetHigh.ticker == ticker)).first()
        if existing is not None and float(existing.all_time_high) > all_time_high:
            all_time_high = float(existing.all_time_high)
            ath_date = existing.ath_date
        write_price_cache(ticker, closes, market=market)
        all_closes_for_latest[ticker] = closes
        records.append(
            {
                "ticker": ticker,
                "name": row.asset["name"],
                "asset_type": row.asset["asset_type"],
                "all_time_high": all_time_high,
                "ath_date": ath_date,
                "cached_at": cached_at,
            }
        )

    imported = (
        batch_upsert(db, AssetHigh, records, ["ticker"]) if records else 0
    )
    latest = anchor_date_excluding_today(
        all_closes_for_latest,
        markets=global_asset_markets(GLOBAL_ASSETS),
    )
    cache_latest_trading_date(
        LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL
    )

    ok = len(errors) == 0 and len(parsed) == len(to_fetch) and (
        latest is not None or not to_fetch
    )
    if ok:
        status = SyncStatus.SUCCESS
        watermark = forward_date(old_date, latest) if latest else old_date
    else:
        status = resolve_status(False, imported)
        watermark = old_date
    last_synced_at = upsert_sync_meta(
        db,
        "asset_high",
        last_synced_date=watermark,
        status=status,
        error="; ".join(errors[:5]) if errors else None,
    )

    result = build_result(
        imported=imported,
        total=len(records),
        last_date=watermark,
        ok=ok,
        source_errors=(
            {"global_assets": "; ".join(errors[:5])} if errors else {}
        ),
        last_synced_at=last_synced_at,
        status=status,
    )
    return finalize_import_result(result, start_ts=start_ts, log_label="全球资产最高点刷新")
