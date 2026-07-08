"""导入结果类型契约。"""

from dataclasses import dataclass
from typing import Any

from astock.core.sync_status import SyncStatus


@dataclass
class ImportResult:
    imported: int
    total: int
    last_date: str | None
    last_synced_at: str | None
    status: SyncStatus
    source_errors: dict[str, str | None] | None = None
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportResult":
        return cls(
            imported=data["imported"],
            total=data["total"],
            last_date=data.get("last_date"),
            last_synced_at=data.get("last_synced_at"),
            status=data["status"],
            source_errors=data.get("source_errors"),
            elapsed=data.get("elapsed"),
        )
