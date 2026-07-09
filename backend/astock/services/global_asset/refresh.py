"""全球资产历史最高点刷新（写路径）。"""

import logging
import time

from sqlmodel import Session

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS
from astock.core.datetime_utils import (
    filter_settled_closes,
    is_multi_market_synced,
    iso_now,
    market_for_asset_type,
)
from astock.core.redis_client import LATEST_TRADING_DATE_KEY, set_string
from astock.core.sync_status import SyncStatus
from astock.models.asset_high import AssetHigh
from astock.services.global_asset._cache import write_price_cache
from astock.services.imports._common import build_result
from astock.services.price_utils import anchor_date_excluding_today, global_asset_markets
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
            result = build_result(
                imported=0,
                total=total,
                last_date=meta.last_synced_date,
                ok=True,
                source_errors={"global_assets": None},
                last_synced_at=meta.last_synced_at,
                elapsed=round(time.perf_counter() - start_ts, 2),
            )
            return result

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
        market = market_for_asset_type(asset["asset_type"])
        write_price_cache(ticker, closes, market=market)
        all_closes_for_latest[ticker] = filter_settled_closes(closes, market)

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
        status=(
            SyncStatus.SUCCESS
            if ok
            else SyncStatus.PARTIAL_FAILURE
            if imported
            else SyncStatus.FAILED
        ),
        error="; ".join(errors[:5]) if errors else None,
    )

    elapsed = time.perf_counter() - start_ts
    result = build_result(
        imported=imported,
        total=len(records),
        last_date=latest,
        ok=ok,
        source_errors={"global_assets": "; ".join(errors[:5]) if errors else None},
        last_synced_at=last_synced_at,
        elapsed=round(elapsed, 2),
    )
    logger.info(
        "全球资产最高点刷新完成: imported=%s total=%s status=%s elapsed=%.2fs",
        result["imported"],
        result["total"],
        result["status"],
        elapsed,
    )
    return result
