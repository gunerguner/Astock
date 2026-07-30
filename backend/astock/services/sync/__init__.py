"""同步基础设施：水位存储、导入结果契约、同步状态查询。"""

from astock.services.sync.results import (
    ImportResult,
    aggregate_status,
    build_result,
    finalize_import_result,
    resolve_status,
)
from astock.services.sync.status import get_sync_status
from astock.services.sync.store import (
    batch_upsert,
    count_macro_rows,
    count_rows,
    get_last_date,
    get_sync_meta,
    get_sync_start_date,
    should_skip_daily_sync,
    upsert_sync_meta,
)

__all__ = [
    "ImportResult",
    "aggregate_status",
    "batch_upsert",
    "build_result",
    "count_macro_rows",
    "count_rows",
    "finalize_import_result",
    "get_last_date",
    "get_sync_meta",
    "get_sync_start_date",
    "get_sync_status",
    "resolve_status",
    "should_skip_daily_sync",
    "upsert_sync_meta",
]
