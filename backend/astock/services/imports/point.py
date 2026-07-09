"""指数点位数据导入（多指数）。"""

import logging
import time

from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import POINT_INDEX_CONFIG, point_sync_meta_key
from astock.core.exceptions import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.models.point import Point
from astock.services.imports._common import aggregate_status, build_result
from astock.services.imports.pipeline import run_daily_import
from astock.services.sync_store import count_rows
from astock.sources.akshare import fetch_cn_index_point
from astock.sources.baostock import fetch_point
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _fetch_point_index(index_code: str, start_date: str) -> SourceFetchResult:
    config = POINT_INDEX_CONFIG[index_code]
    source = str(config.get("source", "baostock"))
    if source == "akshare":
        return fetch_cn_index_point(index_code, start_date=start_date)
    return fetch_point(index_code=index_code, start_date=start_date)


def _index_last_date(db: Session, index_code: str) -> str | None:
    return db.exec(
        select(func.max(Point.date)).where(Point.index_code == index_code)
    ).one()


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

        result = run_daily_import(
            db,
            table_name=table_name,
            model=Point,
            conflict_cols=["date", "index_code"],
            fetch=lambda start, code=index_code: _fetch_point_index(code, start),
            source_key=index_code,
            failure_message=f"{index_name}点位导入失败",
            log_label=f"{index_name}点位",
            prepare_table="point",
            resolve_last_date=lambda s, code=index_code: _index_last_date(s, code),
            raise_on_failed=False,
        )

        total_imported += result["imported"]
        total_rows = count_rows(db, Point)
        statuses.append(result["status"])
        if result.get("last_date"):
            last_dates.append(result["last_date"])
        if result.get("last_synced_at"):
            last_synced_ats.append(result["last_synced_at"])
        err = (result.get("source_errors") or {}).get(index_code)
        source_errors[index_code] = err
        if err:
            all_errors.append(f"{index_name}: {err}")

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
