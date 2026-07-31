"""流式导入进度上报。"""

import json
import time
from collections.abc import Callable, Iterator
from typing import Any, Protocol

from astock.core.sync_status import SyncStatus
from astock.services.sync.results import ImportResult

PHASE_LABELS: dict[str, str] = {
    "turnover": "成交额",
    "point": "指数点位",
    "stock": "个股切片",
    "global_assets": "全球资产",
    "us_macro": "美国宏观",
    "cn_macro": "中国宏观",
}


class SupportsToDict(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SSEBridge:
    """收集 SSE 帧，供同步生成器在步骤间 drain。"""

    def __init__(self) -> None:
        self.frames: list[str] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.frames.append(format_sse(event_type, data))

    def drain(self) -> Iterator[str]:
        while self.frames:
            yield self.frames.pop(0)


class ProgressReporter:
    def __init__(self, emit: Callable[[str, dict[str, Any]], None]) -> None:
        self._emit = emit
        self._phase_start_times: dict[str, float] = {}

    def phase_start(self, key: str) -> None:
        self._phase_start_times[key] = time.perf_counter()
        self._emit(
            "progress",
            {
                "phase": key,
                "label": PHASE_LABELS.get(key, key),
                "status": "running",
                "current": 0,
                "total": 1,
                "imported": 0,
                "elapsed": 0.0,
            },
        )

    def phase_progress(
        self,
        key: str,
        current: int,
        total: int,
        detail: str | None = None,
        *,
        imported: int = 0,
    ) -> None:
        start = self._phase_start_times.get(key, time.perf_counter())
        self._emit(
            "progress",
            {
                "phase": key,
                "label": PHASE_LABELS.get(key, key),
                "status": "running",
                "current": current,
                "total": total,
                "imported": imported,
                "detail": detail,
                "elapsed": round(time.perf_counter() - start, 2),
            },
        )

    def phase_done(self, key: str, result: ImportResult) -> None:
        start = self._phase_start_times.get(key, time.perf_counter())
        elapsed = result.elapsed if result.elapsed > 0 else round(
            time.perf_counter() - start, 2
        )
        self._emit(
            "progress",
            {
                "phase": key,
                "label": PHASE_LABELS.get(key, key),
                "status": "failed" if result.status == SyncStatus.FAILED else "done",
                "current": result.total,
                "total": max(result.total, 1),
                "imported": result.imported,
                "last_date": result.last_date,
                "last_synced_at": result.last_synced_at,
                "source_errors": result.source_errors or {},
                "elapsed": elapsed,
            },
        )

    def error(self, message: str) -> None:
        self._emit("error", {"message": message})

    def done(self, result: SupportsToDict) -> None:
        self._emit("done", result.to_dict())

    def ping(self) -> None:
        self._emit("ping", {})
