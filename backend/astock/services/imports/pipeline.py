"""日频数据集导入模板（Template Method）。"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from astock.core.exceptions import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.services.imports._common import (
    aggregate_status,
    build_result,
    build_skip_result,
    finalize_import_result,
    prepare_records_for_upsert,
    resolve_status,
)
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_start_date,
    should_skip_daily_sync,
    upsert_sync_meta,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


@dataclass
class DailyImportSpec:
    """单表日频导入配置。"""

    table_name: str
    model: type
    conflict_cols: list[str]
    fetch: Callable[[str], SourceFetchResult]
    source_key: str
    failure_message: str
    log_label: str
    prepare_table: str | None = None
    resolve_last_date: Callable[[Session], str | None] | None = None
    error_label: str | None = None


def run_daily_import(
    db: Session,
    spec: DailyImportSpec,
    *,
    raise_on_failed: bool = True,
) -> dict:
    """单表日频导入编排：可跳过、拉取、校验、入库并更新同步水位。

    raise_on_failed 为 True 时，整体 FAILED 会抛 ExternalSourceAppError。
    """
    start_ts = time.perf_counter()
    last_date_fn = spec.resolve_last_date or (lambda s: get_last_date(s, spec.model))
    db_last_date = last_date_fn(db)

    if should_skip_daily_sync(db, spec.table_name):
        result = build_skip_result(
            db,
            table_name=spec.table_name,
            model=spec.model,
            start_ts=start_ts,
            last_date=db_last_date,
        )
        logger.info(
            "%s导入跳过: 无新交易日 (last_date=%s)",
            spec.log_label,
            db_last_date,
        )
        return result

    start_date = get_sync_start_date(db, spec.table_name)
    fr = spec.fetch(start_date)
    records = prepare_records_for_upsert(
        spec.prepare_table or spec.table_name, fr.records, fr=fr
    )
    imported = batch_upsert(
        db,
        spec.model,
        records,
        spec.conflict_cols,
        commit_mode="single",
    )

    last_date = last_date_fn(db)
    status = resolve_status(fr.ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        spec.table_name,
        last_synced_date=last_date,
        status=status,
        error=fr.error_summary() if not fr.ok else None,
    )

    result = build_result(
        imported=imported,
        total=count_rows(db, spec.model),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map(spec.source_key),
        last_synced_at=last_synced_at,
    )

    if raise_on_failed and result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"{spec.failure_message}: {result['source_errors'].get(spec.source_key)}"
        )

    return finalize_import_result(result, start_ts=start_ts, log_label=f"{spec.log_label}导入")


def run_multi_daily_import(
    db: Session,
    specs: list[DailyImportSpec],
    *,
    aggregate_failure_message: str,
    log_label: str,
    count_model: type,
) -> dict:
    """多实体日频导入：逐项 run_daily_import 后聚合 status / errors。"""
    start_ts = time.perf_counter()
    total_imported = 0
    all_errors: list[str] = []
    source_errors: dict[str, str] = {}
    last_dates: list[str] = []
    last_synced_ats: list[str] = []
    statuses: list[SyncStatus] = []

    for spec in specs:
        error_label = spec.error_label or spec.log_label
        result = run_daily_import(db, spec, raise_on_failed=False)

        total_imported += result["imported"]
        statuses.append(result["status"])
        if result.get("last_date"):
            last_dates.append(result["last_date"])
        if result.get("last_synced_at"):
            last_synced_ats.append(result["last_synced_at"])
        err = (result.get("source_errors") or {}).get(spec.source_key)
        if err:
            source_errors[spec.source_key] = err
            all_errors.append(f"{error_label}: {err}")

    ok = len(all_errors) == 0
    result = build_result(
        imported=total_imported,
        total=count_rows(db, count_model),
        last_date=max(last_dates) if last_dates else None,
        ok=ok,
        source_errors=source_errors,
        last_synced_at=max(last_synced_ats) if last_synced_ats else None,
    )
    result["status"] = aggregate_status(*statuses)

    if result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"{aggregate_failure_message}: {'; '.join(all_errors[:5])}"
        )

    return finalize_import_result(result, start_ts=start_ts, log_label=log_label)
