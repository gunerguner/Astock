"""导入结果类型契约与状态组装。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from astock.core.sync_status import SyncStatus

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    imported: int
    total: int
    last_date: str | None
    last_synced_at: str | None
    status: SyncStatus
    source_errors: dict[str, str] = field(default_factory=dict)
    elapsed: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "imported": self.imported,
            "total": self.total,
            "last_date": self.last_date,
            "last_synced_at": self.last_synced_at,
            "status": self.status,
            "source_errors": self.source_errors,
        }
        if self.elapsed is not None:
            d["elapsed"] = self.elapsed
        return d


def resolve_status(ok: bool, imported: int) -> SyncStatus:
    """根据抓取成功与否与入库条数判定 SUCCESS/PARTIAL/FAILED。"""
    if ok:
        return SyncStatus.SUCCESS
    if imported > 0:
        return SyncStatus.PARTIAL_FAILURE
    return SyncStatus.FAILED


def aggregate_status(*statuses: SyncStatus | str) -> SyncStatus:
    """聚合多项导入状态，任一项失败则整体为部分失败。"""
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
    source_errors: dict[str, str] | None = None,
    last_synced_at: str | None = None,
    elapsed: float | None = None,
) -> dict[str, Any]:
    """组装标准导入结果字典（含 status、source_errors、elapsed）。"""
    result = ImportResult(
        imported=imported,
        total=total,
        last_date=last_date,
        last_synced_at=last_synced_at,
        status=resolve_status(ok, imported),
        source_errors=source_errors if source_errors is not None else {},
        elapsed=elapsed,
    )
    return result.to_dict()


def finalize_import_result(
    result: dict[str, Any],
    *,
    start_ts: float,
    log_label: str,
) -> dict[str, Any]:
    """记录导入耗时日志并写回结果 elapsed 字段。"""
    elapsed = time.perf_counter() - start_ts
    logger.info(
        "%s完成: imported=%s total=%s status=%s elapsed=%.2fs",
        log_label,
        result["imported"],
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result
