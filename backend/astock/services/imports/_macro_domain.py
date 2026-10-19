"""宏观领域月频导入模板（写入统一 macro_value 长表）。"""


import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session

from astock.core.datetime_utils import iso_now, today_local_date
from astock.core.sync_status import SyncStatus
from astock.datasets.macro.types import MacroMetric, MacroRegion
from astock.datasets.result import FetchResult
from astock.models.macro import MacroValue
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


def run_macro_import(
    db: Session,
    *,
    region: MacroRegion,
    sync_table: str,
    refresh_day: int,
    fetch_fn: Callable[[], FetchResult],
    log_label: str,
    required_metrics: tuple[MacroMetric, ...],
) -> ImportResult:
    """拉取宏观月度指标并 upsert；尊重月频跳过窗口。"""
    start_ts = time.perf_counter()
    skip, meta = should_skip_macro(
        db,
        region=region,
        sync_table=sync_table,
        refresh_day=refresh_day,
    )
    if skip:
        if meta is None:
            raise RuntimeError(f"{sync_table}: should_skip_macro 为真但 sync_meta 缺失")
        total = count_macro_rows(db, region)
        logger.info(
            "%s刷新跳过: 已覆盖期望月份 (last_synced_date=%s expected=%s refresh_day=%s)",
            log_label,
            meta.last_synced_date,
            expected_macro_period(refresh_day=refresh_day),
            refresh_day,
        )
        return build_result(
            imported=0,
            total=total,
            last_date=meta.last_synced_date,
            ok=True,
            source_errors={},
            last_synced_at=meta.last_synced_at,
            elapsed=round(time.perf_counter() - start_ts, 2),
        )

    fr = fetch_fn()
    cached_at = iso_now()
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

    if not records:
        error = fr.error_summary() or f"{log_label}拉取失败"
        old_meta = get_sync_meta(db, sync_table)
        last_synced_at = upsert_sync_meta(
            db,
            sync_table,
            last_synced_date=old_meta.last_synced_date if old_meta else None,
            status=SyncStatus.FAILED,
            error=error,
        )
        result = build_result(
            imported=0,
            total=count_macro_rows(db, region),
            last_date=old_meta.last_synced_date if old_meta else None,
            ok=False,
            source_errors=fr.to_error_map(sync_table),
            last_synced_at=last_synced_at,
        )
        return finalize_import_result(
            result, start_ts=start_ts, log_label=f"{log_label}刷新"
        )

    imported = batch_upsert(db, MacroValue, records, _CONFLICT_COLS)
    latest = _latest_cpi_period(records)
    expected = expected_macro_period(refresh_day=refresh_day)
    old_meta = get_sync_meta(db, sync_table)
    old_date = old_meta.last_synced_date if old_meta else None
    covered = bool(latest) and _metrics_cover(records, required_metrics, expected)
    if not latest:
        fr.errors.append("本次没有有效 CPI，水位保持不变")
        fr.ok = False
    elif latest < expected or not covered or not fr.ok:
        missing = [
            metric
            for metric in required_metrics
            if expected not in _metric_periods(records).get(metric, set())
        ]
        if latest < expected:
            fr.errors.append(f"源端最新 CPI 月份 {latest} 尚未覆盖期望 {expected}")
        if missing:
            fr.errors.append(f"期望月份 {expected} 缺少指标: {','.join(missing)}")
        fr.ok = False

    if fr.ok and covered and latest:
        status = SyncStatus.SUCCESS
        watermark = forward_date(old_date, latest)
    elif imported > 0:
        status = SyncStatus.PARTIAL_FAILURE
        watermark = old_date
    else:
        status = SyncStatus.FAILED
        watermark = old_date

    last_synced_at = upsert_sync_meta(
        db,
        sync_table,
        last_synced_date=watermark,
        status=status,
        error=None if status == SyncStatus.SUCCESS else fr.error_summary(),
    )
    result = build_result(
        imported=imported,
        total=count_macro_rows(db, region),
        last_date=watermark,
        ok=status == SyncStatus.SUCCESS,
        source_errors=fr.to_error_map(sync_table) if fr.errors else {},
        last_synced_at=last_synced_at,
        status=status,
    )
    return finalize_import_result(
        result, start_ts=start_ts, log_label=f"{log_label}刷新"
    )
