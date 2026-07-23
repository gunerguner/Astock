"""导入结果类型契约。"""

from dataclasses import dataclass, field
from typing import Any

from astock.core.sync_status import SyncStatus


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
