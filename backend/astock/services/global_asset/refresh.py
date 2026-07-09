"""全球资产历史最高点刷新（写路径）。"""

import logging
import time

from sqlmodel import Session

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS
from astock.core.datetime_utils import is_multi_market_synced, iso_now
from astock.core.price_utils import anchor_date_excluding_today, global_asset_markets
from astock.core.redis_client import LATEST_TRADING_DATE_KEY, set_string
from astock.core.sync_status import SyncStatus
from astock.models.asset_high import AssetHigh
from astock.services.global_asset._cache import parse_asset_fetch_results, write_price_cache
from astock.services.imports._common import build_result, finalize_import_result, resolve_status
from astock.services.sync_store import batch_upsert, count_rows, get_sync_meta, upsert_sync_meta
from astock.sources.akshare import fetch_all_assets

logger = logging.getLogger(__name__)


def refresh_asset_highs(db: Session) -> dict:
    start_ts = time.perf_counter()
    meta = get_sync_meta(db, "asset_high")
    if (
        meta
        and meta.last_status == SyncStatus.SUCCESS
        and is_multi_market_synced(meta.last_synced_date)
    ):
        total = count_rows(db, AssetHigh)
        if total > 0:
            logger.info(
                "全球资产最高点刷新跳过: 已覆盖最近可结算日 (last_synced_date=%s)",
                meta.last_synced_date,
            )
            return build_result(
                imported=0,
                total=total,
                last_date=meta.last_synced_date,
                ok=True,
                source_errors={"global_assets": None},
                last_synced_at=meta.last_synced_at,
                elapsed=round(time.perf_counter() - start_ts, 2),
            )

    cached_at = iso_now()
    records: list[dict] = []
    all_closes_for_latest: dict[str, dict[str, float]] = {}

    parsed, errors = parse_asset_fetch_results(
        GLOBAL_ASSETS, fetch_all_assets(), skip_pending=True
    )
    for asset, record, market, closes in parsed:
        ticker = asset["ticker"]
        try:
            all_time_high = float(record["all_time_high"])
            ath_date = str(record["ath_date"])
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{ticker}: 历史最高点数据无效 ({e})")
            continue
        write_price_cache(ticker, closes, market=market)
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
    latest = anchor_date_excluding_today(
        all_closes_for_latest,
        markets=global_asset_markets(GLOBAL_ASSETS),
    )
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)

    ok = len(errors) == 0
    last_synced_at = upsert_sync_meta(
        db,
        "asset_high",
        last_synced_date=latest,
        status=resolve_status(ok, imported),
        error="; ".join(errors[:5]) if errors else None,
    )

    result = build_result(
        imported=imported,
        total=len(records),
        last_date=latest,
        ok=ok,
        source_errors={"global_assets": "; ".join(errors[:5]) if errors else None},
        last_synced_at=last_synced_at,
    )
    return finalize_import_result(result, start_ts=start_ts, log_label="全球资产最高点刷新")
