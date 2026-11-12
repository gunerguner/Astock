"""宏观领域月频导入模板（写入统一 macro_value 长表）。"""


import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session

from astock.core.datetime_utils import iso_now, today_local_date
from astock.core.sync_status import SyncStatus
from astock.datasets.macro.types import MacroMetric, MacroRegion
from astock.datasets.result import FetchResult
from astock.models.macro import MacroValue
from astock.services.imports._common import build_skip_result
from astock.services.sync.results import (
    ImportResult,
    build_result,
    finalize_import_result,
)
from astock.services.sync.store import (
    batch_upsert,
    count_macro_rows,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.services.sync.watermark import forward_date

logger = logging.getLogger(__name__)

_CONFLICT_COLS = ["region", "period", "metric"]
WATERMARK_METRIC = "cpi_yoy"


def expected_macro_period(
    today: date | None = None,
    *,
    refresh_day: int,
) -> str:
    """北京时间下当前应覆盖的最新宏观月份。

    - 每月 refresh_day（含）之后：期望上月已发布
    - 此前：仅期望上上月
    """
    now = today or today_local_date()
    first = now.replace(day=1)
    prev_month_last = first - timedelta(days=1)
    if now.day >= refresh_day:
        return prev_month_last.strftime("%Y-%m")
    earlier_last = prev_month_last.replace(day=1) - timedelta(days=1)
    return earlier_last.strftime("%Y-%m")


def should_skip_macro(
    db: Session,
    *,
    region: MacroRegion,
    sync_table: str,
    refresh_day: int,
):
    """水位已覆盖期望月份且上次成功、该 region 有数据时可跳过；返回 (是否跳过, sync_meta)。"""
    meta = get_sync_meta(db, sync_table)
    if not meta or not meta.last_synced_date:
        return False, meta
    if meta.last_status != SyncStatus.SUCCESS:
        return False, meta
    if count_macro_rows(db, region) <= 0:
        return False, meta
    expected = expected_macro_period(refresh_day=refresh_day)
    return str(meta.last_synced_date) >= expected, meta


def _latest_cpi_period(records: list[dict[str, Any]]) -> str | None:
    periods = [
        str(r["period"])
        for r in records
        if r.get("period") and r.get("metric") == WATERMARK_METRIC and r.get("value") is not None
    ]
    return max(periods) if periods else None


def _metric_periods(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for row in records:
        metric = str(row.get("metric") or "")
        period = str(row.get("period") or "")
        if metric and period and row.get("value") is not None:
            found.setdefault(metric, set()).add(period)
    return found


def _metrics_cover(records: list[dict[str, Any]], metrics: tuple[str, ...], period: str) -> bool:
    found = _metric_periods(records)
    return all(period in found.get(metric, set()) for metric in metrics)


@dataclass(frozen=True)
class MacroImportSpec:
    """单区域月频宏观导入配置。"""

    region: MacroRegion
    sync_table: str
    refresh_day: int
    fetch_fn: Callable[[], FetchResult]
    log_label: str
    required_metrics: tuple[MacroMetric, ...]


def _macro_records(
    region: MacroRegion,
    fr: FetchResult,
    cached_at: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in fr.records:
        period = str(row.get("period") or "")
        metric = str(row.get("metric") or "")
        value = row.get("value")
        if not period or not metric or value is None:
            continue
        records.append(
            {
                "region": region,
                "period": period,
                "metric": metric,
                "value": float(value),
                "cached_at": cached_at,
            }
        )
    return records


def _failed_empty(
    db: Session,
    spec: MacroImportSpec,
    fr: FetchResult,
    start_ts: float,
) -> ImportResult:
    error = fr.error_summary() or f"{spec.log_label}拉取失败"
    old_meta = get_sync_meta(db, spec.sync_table)
    last_synced_at = upsert_sync_meta(
        db,
        spec.sync_table,
        last_synced_date=old_meta.last_synced_date if old_meta else None,
        status=SyncStatus.FAILED,
        error=error,
    )
    result = build_result(
        imported=0,
        total=count_macro_rows(db, spec.region),
        last_date=old_meta.last_synced_date if old_meta else None,
        ok=False,
        source_errors=fr.to_error_map(spec.sync_table),
        last_synced_at=last_synced_at,
    )
    return finalize_import_result(
        result, start_ts=start_ts, log_label=f"{spec.log_label}刷新"
    )


def _resolve_macro_status(
    fr: FetchResult,
    records: list[dict[str, Any]],
    spec: MacroImportSpec,
    *,
    imported: int,
    old_date: str | None,
) -> tuple[SyncStatus, str | None]:
    latest = _latest_cpi_period(records)
    expected = expected_macro_period(refresh_day=spec.refresh_day)
    covered = bool(latest) and _metrics_cover(records, spec.required_metrics, expected)
    if not latest:
        fr.errors.append("本次没有有效 CPI，水位保持不变")
        fr.ok = False
    elif latest < expected or not covered or not fr.ok:
        found = _metric_periods(records)
        missing = [
            metric for metric in spec.required_metrics if expected not in found.get(metric, set())
        ]
        if latest < expected:
            fr.errors.append(f"源端最新 CPI 月份 {latest} 尚未覆盖期望 {expected}")
        if missing:
            fr.errors.append(f"期望月份 {expected} 缺少指标: {','.join(missing)}")
        fr.ok = False

    if fr.ok and covered and latest:
        return SyncStatus.SUCCESS, forward_date(old_date, latest)
    if imported > 0:
        return SyncStatus.PARTIAL_FAILURE, old_date
    return SyncStatus.FAILED, old_date


def run_macro_import(db: Session, spec: MacroImportSpec) -> ImportResult:
    """拉取宏观月度指标并 upsert；尊重月频跳过窗口。"""
    start_ts = time.perf_counter()
    skip, meta = should_skip_macro(
        db,
        region=spec.region,
        sync_table=spec.sync_table,
        refresh_day=spec.refresh_day,
    )
    if skip and meta is not None:
        logger.info(
            "%s刷新跳过: 已覆盖期望月份 (last_synced_date=%s expected=%s refresh_day=%s)",
            spec.log_label,
            meta.last_synced_date,
            expected_macro_period(refresh_day=spec.refresh_day),
            spec.refresh_day,
        )
        return build_skip_result(
            db,
            table_name=spec.sync_table,
            start_ts=start_ts,
            last_date=meta.last_synced_date,
            total=count_macro_rows(db, spec.region),
            touch_meta=False,
        )

    fr = spec.fetch_fn()
    records = _macro_records(spec.region, fr, iso_now())
    if not records:
        return _failed_empty(db, spec, fr, start_ts)

    imported = batch_upsert(db, MacroValue, records, _CONFLICT_COLS)
    old_meta = get_sync_meta(db, spec.sync_table)
    status, watermark = _resolve_macro_status(
        fr,
        records,
        spec,
        imported=imported,
        old_date=old_meta.last_synced_date if old_meta else None,
    )
    last_synced_at = upsert_sync_meta(
        db,
        spec.sync_table,
        last_synced_date=watermark,
        status=status,
        error=None if status == SyncStatus.SUCCESS else fr.error_summary(),
    )
    result = build_result(
        imported=imported,
        total=count_macro_rows(db, spec.region),
        last_date=watermark,
        ok=status == SyncStatus.SUCCESS,
        source_errors=fr.to_error_map(spec.sync_table) if fr.errors else {},
        last_synced_at=last_synced_at,
        status=status,
    )
    return finalize_import_result(
        result, start_ts=start_ts, log_label=f"{spec.log_label}刷新"
    )
