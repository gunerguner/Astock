"""指数点位数据导入（多指数）。"""

import logging
import time

from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import POINT_INDEX_CONFIG, point_sync_meta_key
from astock.core.exceptions import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.models.point import Point
from astock.services.imports._common import (
    aggregate_status,
    build_result,
    build_skip_result,
    prepare_records_for_upsert,
    resolve_status,
)
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_sync_start_date,
    should_skip_daily_sync,
    upsert_sync_meta,
)
from astock.sources.akshare_client import fetch_cn_index_point
from astock.sources.baostock import fetch_point
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _fetch_point_index(index_code: str, start_date: str) -> SourceFetchResult:
    config = POINT_INDEX_CONFIG[index_code]
    source = str(config.get("source", "baostock"))
    if source == "akshare":
        return fetch_cn_index_point(index_code, start_date=start_date)
    return fetch_point(index_code=index_code, start_date=start_date)


def import_point(db: Session) -> dict:
    start_ts = time.perf_counter()
    total_imported = 0
    total_rows = count_rows(db, Point)
    all_errors: list[str] = []
    source_errors: dict[str, str | None] = {}
    last_dates: list[str] = []
    last_synced_ats: list[str] = []
    statuses: list[SyncStatus] = []

    for index_code, config in POINT_INDEX_CONFIG.items():
        index_name = str(config["name"])
        table_name = point_sync_meta_key(index_code)
        index_last_date = db.exec(
            select(func.max(Point.date)).where(Point.index_code == index_code)
        ).one()

        if should_skip_daily_sync(db, table_name):
            skip_result = build_skip_result(
                db,
                table_name=table_name,
                model=Point,
                source_key=index_code,
                start_ts=time.perf_counter(),
                last_date=index_last_date,
            )
            if index_last_date:
                last_dates.append(index_last_date)
            if skip_result.get("last_synced_at"):
                last_synced_ats.append(skip_result["last_synced_at"])
            statuses.append(SyncStatus.SUCCESS)
            source_errors[index_code] = None
            logger.info(
                "%s点位导入跳过: 无新交易日 (last_date=%s)",
                index_name,
                index_last_date,
            )
            continue

        start_date = get_sync_start_date(db, table_name)

        fr = _fetch_point_index(index_code, start_date)
        records = prepare_records_for_upsert("point", fr.records, fr=fr)
        imported = batch_upsert(
            db,
            Point,
            records,
            ["date", "index_code"],
            commit_mode="single",
        )

        last_date = db.exec(
            select(func.max(Point.date)).where(Point.index_code == index_code)
        ).one()
        status = resolve_status(fr.ok, imported)
        last_synced_at = upsert_sync_meta(
            db,
            table_name,
            last_synced_date=last_date,
            status=status,
            error=fr.error_summary() if not fr.ok else None,
        )

        total_imported += imported
        total_rows = count_rows(db, Point)
        statuses.append(status)
        if last_date:
            last_dates.append(last_date)
        if last_synced_at:
            last_synced_ats.append(last_synced_at)
        if not fr.ok:
            all_errors.append(f"{index_name}: {fr.error_summary()}")
        source_errors[index_code] = fr.error_summary() if not fr.ok else None

        logger.info(
            "%s点位导入: imported=%s status=%s",
            index_name,
            imported,
            status,
        )

    ok = len(all_errors) == 0
    aggregate_status_val = aggregate_status(*statuses)
    result = build_result(
        imported=total_imported,
        total=total_rows,
        last_date=max(last_dates) if last_dates else None,
        ok=ok,
        source_errors=source_errors if source_errors else None,
        last_synced_at=max(last_synced_ats) if last_synced_ats else None,
    )
    result["status"] = aggregate_status_val

    if result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"指数点位导入失败: {'; '.join(all_errors[:5])}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "指数点位导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        total_imported,
        total_rows,
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result
