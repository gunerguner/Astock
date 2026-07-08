"""全球资产历史最高点刷新（写路径）。"""

import logging

from sqlmodel import Session, select

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS
from astock.core.datetime_utils import iso_now, synced_today
from astock.core.redis_client import LATEST_TRADING_DATE_KEY, set_string
from astock.core.sync_status import SyncStatus
from astock.models.asset_high import AssetHigh
from astock.services.global_asset._cache import write_price_cache
from astock.services.price_utils import latest_trading_date
from astock.services.sync_store import batch_upsert, get_sync_meta, upsert_sync_meta
from astock.sources.akshare_client import fetch_all_assets

logger = logging.getLogger(__name__)


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
        write_price_cache(ticker, closes)
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
