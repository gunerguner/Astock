"""个股导入上下文与缓冲写入。"""

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from astock.config import START_DATE, STOCK_TURNOVER_SLICE_THRESHOLD, STOCK_UPSERT_FLUSH_SIZE
from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.core.sync_status import SyncStatus
from astock.models.stock_turnover import StockTurnover
from astock.services.imports._common import (
    build_result,
    finalize_import_result,
    is_missing_value,
    resolve_status,
)
from astock.services.sync_store import batch_upsert, count_rows, upsert_sync_meta
from astock.sources.fetch_result import SourceFetchResult


@dataclass
class StockImportContext:
    db: Session
    on_progress: ProgressReporter | None = None
    bridge: SSEBridge | None = None
    start_ts: float = field(default_factory=time.perf_counter)
    is_skipped: bool = False
    errors: list[str] = field(default_factory=list)
    stock_errors: list[str] = field(default_factory=list)
    imported: int = 0
    record_buffer: list[dict[str, Any]] = field(default_factory=list)
    code_to_name: dict[str, str] = field(default_factory=dict)
    snapshot_by_code: dict[str, dict[str, Any]] = field(default_factory=dict)
    big_cap_codes: list[str] = field(default_factory=list)
    path_b_codes: list[str] = field(default_factory=list)
    total_stocks: int = 0
    tasks: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    as_of_date: str | None = None
    last_synced: str | None = None
    hist_start_date: str = START_DATE
    hist_end_date: str | None = None
    use_snapshot_for_as_of: bool = False
    cached_at: str = ""

    def flush_buffer(self) -> None:
        if not self.record_buffer:
            return
        self.imported += batch_upsert(
            self.db,
            StockTurnover,
            self.record_buffer,
            ["date", "code"],
            commit_mode="single",
        )
        self.record_buffer = []

    def emit_stock_progress(self, current: int) -> Iterator[str]:
        if self.on_progress is not None:
            self.on_progress.phase_progress(
                "stock",
                current,
                self.total_stocks,
                f"个股日线 {current}/{self.total_stocks}",
                imported=self.imported,
            )
        if self.bridge is not None:
            yield from self.bridge.drain()

    def accumulate(self, code: str, hist_fr: SourceFetchResult) -> None:
        if not hist_fr.ok:
            self.stock_errors.extend(hist_fr.errors)
            return

        name = self.code_to_name.get(code, "")
        if is_missing_value(name):
            self.stock_errors.append(f"个股 {code}: 缺少股票名称")
            return

        self.record_buffer.extend(
            {
                "date": row["date"],
                "code": code,
                "name": name,
                "amount": row["amount"],
                "cached_at": self.cached_at,
            }
            for row in hist_fr.records
            if not is_missing_value(row.get("amount"))
            and row["amount"] >= STOCK_TURNOVER_SLICE_THRESHOLD
        )

    def maybe_flush(self) -> None:
        if len(self.record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
            self.flush_buffer()

    def append_snapshot_slice(self, date: str) -> int:
        """从快照直写 as_of 日切片，返回写入缓冲条数。"""
        added = 0
        for code in self.big_cap_codes:
            spot = self.snapshot_by_code.get(code)
            if not spot:
                continue
            amount = spot.get("amount")
            if is_missing_value(amount) or amount < STOCK_TURNOVER_SLICE_THRESHOLD:
                continue
            name = self.code_to_name.get(code) or spot.get("name") or ""
            if is_missing_value(name):
                self.stock_errors.append(f"个股 {code}: 缺少股票名称")
                continue
            self.record_buffer.append(
                {
                    "date": date,
                    "code": code,
                    "name": name,
                    "amount": float(amount),
                    "cached_at": self.cached_at,
                }
            )
            added += 1
        return added

    def build_result(self) -> dict[str, Any]:
        all_errors = self.errors + self.stock_errors
        ok = len(all_errors) == 0
        status = resolve_status(ok, self.imported)
        last_synced_at = upsert_sync_meta(
            self.db,
            "stock_turnover",
            last_synced_date=self.as_of_date,
            status=status,
            error="; ".join(all_errors[:5]) if all_errors else None,
        )

        result = build_result(
            imported=self.imported,
            total=count_rows(self.db, StockTurnover),
            last_date=self.as_of_date,
            ok=ok,
            source_errors={"stock": "; ".join(all_errors[:5]) if all_errors else None},
            last_synced_at=last_synced_at,
        )

        if result["status"] == SyncStatus.FAILED:
            raise ExternalSourceAppError(
                f"个股切片导入失败: {result['source_errors'].get('stock')}"
            )

        return finalize_import_result(
            result, start_ts=self.start_ts, log_label="个股切片导入"
        )
