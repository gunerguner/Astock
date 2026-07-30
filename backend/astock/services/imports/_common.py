"""导入器公共工具（记录校验与跳过结果）。"""

import time
from typing import Any

from sqlmodel import Session, SQLModel

from astock.core.sync_status import SyncStatus
from astock.datasets.result import FetchResult
from astock.services.sync.results import ImportResult, build_result
from astock.services.sync.store import count_rows, get_sync_meta, upsert_sync_meta

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "point": ["index_code", "close", "cached_at"],
    "turnover": ["sse_amount", "szse_amount", "turnover", "cached_at"],
    "stock_turnover": ["name", "amount", "cached_at"],
    "macro_value": ["value", "cached_at"],
}


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def filter_required_records(
    records: list[dict[str, Any]],
    required_fields: list[str],
    label: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    for record in records:
        missing = [field for field in required_fields if is_missing_value(record.get(field))]
        if missing:
            identity = record.get("date") or record.get("code") or "unknown"
            errors.append(f"{label}: 缺失字段 {','.join(missing)} ({identity})")
            continue
        valid.append(record)
    return valid, errors


def prepare_records_for_upsert(
    table_name: str,
    records: list[dict[str, Any]],
    *,
    fr: FetchResult,
) -> list[dict[str, Any]]:
    """按表名校验必填字段，不合格记录记入抓取错误并剔除。"""
    required_fields = _REQUIRED_FIELDS.get(table_name)
    if not required_fields:
        return records
    valid_records, filter_errors = filter_required_records(
        records,
        required_fields,
        table_name,
    )
    if filter_errors:
        fr.errors.extend(filter_errors)
        fr.ok = False
    return valid_records


def build_skip_result(
    db: Session,
    *,
    table_name: str,
    model: type[SQLModel],
    start_ts: float,
    last_date: str | None = None,
) -> ImportResult:
    """日频数据集无新交易日时的快速跳过结果。"""
    meta = get_sync_meta(db, table_name)
    last_synced = meta.last_synced_date if meta else None
    resolved_last_date = last_date if last_date is not None else last_synced
    last_synced_at = upsert_sync_meta(
        db,
        table_name,
        last_synced_date=last_synced,
        status=SyncStatus.SUCCESS,
        error=None,
    )
    elapsed = time.perf_counter() - start_ts
    return build_result(
        imported=0,
        total=count_rows(db, model),
        last_date=resolved_last_date,
        ok=True,
        source_errors={},
        last_synced_at=last_synced_at,
        elapsed=round(elapsed, 2),
    )
