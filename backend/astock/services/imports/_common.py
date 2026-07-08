"""导入器公共工具。"""

from typing import Any

from astock.core.sync_status import SyncStatus
from astock.sources.fetch_result import SourceFetchResult

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "point": ["index_code", "close", "cached_at"],
    "turnover": ["sse_amount", "szse_amount", "turnover", "cached_at"],
    "stock_turnover": ["name", "amount", "cached_at"],
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
    fr: SourceFetchResult,
) -> list[dict[str, Any]]:
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


def resolve_status(ok: bool, imported: int) -> SyncStatus:
    if ok:
        return SyncStatus.SUCCESS
    if imported > 0:
        return SyncStatus.PARTIAL_FAILURE
    return SyncStatus.FAILED


def aggregate_status(*statuses: SyncStatus | str) -> SyncStatus:
    if all(s == SyncStatus.SUCCESS for s in statuses):
        return SyncStatus.SUCCESS
    if all(s == SyncStatus.FAILED for s in statuses):
        return SyncStatus.FAILED
    return SyncStatus.PARTIAL_FAILURE


def build_result(
    *,
    imported: int,
    total: int,
    last_date: str | None,
    ok: bool,
    source_errors: dict[str, str | None] | None = None,
    last_synced_at: str | None = None,
    elapsed: float | None = None,
) -> dict[str, Any]:
    from astock.services.import_results import ImportResult

    result = ImportResult(
        imported=imported,
        total=total,
        last_date=last_date,
        last_synced_at=last_synced_at,
        status=resolve_status(ok, imported),
        source_errors=source_errors,
        elapsed=elapsed,
    )
    return result.to_dict()
