"""日频数据集导入模板（Template Method）。"""

import logging
import time
from collections.abc import Callable

from sqlmodel import Session

from astock.core.exceptions import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.services.imports._common import (
    build_result,
    build_skip_result,
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


def run_daily_import(
    db: Session,
    *,
    table_name: str,
    model: type,
    conflict_cols: list[str],
    fetch: Callable[[str], SourceFetchResult],
    source_key: str,
    failure_message: str,
    log_label: str,
    prepare_table: str | None = None,
    resolve_last_date: Callable[[Session], str | None] | None = None,
    raise_on_failed: bool = True,
) -> dict:
    """skip → fetch → validate → upsert → meta → result。"""
    start_ts = time.perf_counter()
    last_date_fn = resolve_last_date or (lambda s: get_last_date(s, model))
    db_last_date = last_date_fn(db)

    if should_skip_daily_sync(db, table_name):
        result = build_skip_result(
            db,
            table_name=table_name,
            model=model,
            source_key=source_key,
            start_ts=start_ts,
            last_date=db_last_date,
        )
        logger.info(
            "%s导入跳过: 无新交易日 (last_date=%s)",
            log_label,
            db_last_date,
        )
        return result

    start_date = get_sync_start_date(db, table_name)
    fr = fetch(start_date)
    records = prepare_records_for_upsert(
        prepare_table or table_name, fr.records, fr=fr
    )
    imported = batch_upsert(
        db,
        model,
        records,
        conflict_cols,
        commit_mode="single",
    )

    last_date = last_date_fn(db)
    status = resolve_status(fr.ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        table_name,
        last_synced_date=last_date,
        status=status,
        error=fr.error_summary() if not fr.ok else None,
    )

    result = build_result(
        imported=imported,
        total=count_rows(db, model),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map(source_key),
        last_synced_at=last_synced_at,
    )

    if raise_on_failed and result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"{failure_message}: {result['source_errors'].get(source_key)}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "%s导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        log_label,
        imported,
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result
