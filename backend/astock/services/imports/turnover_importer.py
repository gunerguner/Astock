"""成交额数据导入。"""

import logging
import time
from collections.abc import Callable

from sqlmodel import Session

from astock.core.exceptions import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.models.turnover import Turnover
from astock.services.imports._common import build_result, prepare_records_for_upsert, resolve_status
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_start_date,
    upsert_sync_meta,
)
from astock.sources.baostock import fetch_turnover
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _import_simple_dataset(
    db: Session,
    *,
    table_name: str,
    model: type,
    conflict_cols: list[str],
    fetch: Callable[[str], SourceFetchResult],
    source_key: str,
    failure_message: str,
    log_label: str,
) -> dict:
    start_ts = time.perf_counter()
    start_date = get_sync_start_date(db, table_name)

    fr = fetch(start_date)
    records = prepare_records_for_upsert(table_name, fr.records, fr=fr)
    imported = batch_upsert(
        db,
        model,
        records,
        conflict_cols,
        commit_mode="single",
    )

    last_date = get_last_date(db, model)
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

    if result["status"] == SyncStatus.FAILED:
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


def import_turnover(db: Session) -> dict:
    return _import_simple_dataset(
        db,
        table_name="turnover",
        model=Turnover,
        conflict_cols=["date"],
        fetch=fetch_turnover,
        source_key="turnover",
        failure_message="成交额导入失败",
        log_label="成交额",
    )
