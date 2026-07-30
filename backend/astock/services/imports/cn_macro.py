"""中国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session

from astock.config import CN_MACRO_REFRESH_DAY
from astock.core.datetime_utils import iso_now
from astock.core.sync_status import SyncStatus
from astock.models.macro import METRIC_CPI_YOY, REGION_CN, MacroValue
from astock.services.imports._common import (
    build_result,
    finalize_import_result,
    resolve_status,
)
from astock.services.sync_store import (
    batch_upsert,
    count_macro_rows,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.sources.cn_macro import fetch_cn_macro

logger = logging.getLogger(__name__)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SYNC_TABLE = "cn_macro"
_CONFLICT_COLS = ["region", "period", "metric"]


def _today_shanghai() -> date:
    return datetime.now(_SHANGHAI).date()


def expected_cn_macro_period(
    today: date | None = None,
    *,
    refresh_day: int = CN_MACRO_REFRESH_DAY,
) -> str:
    """北京时间下当前应覆盖的最新宏观月份。

    - 每月 refresh_day（含）之后：期望上月已发布
    - 此前：仅期望上上月
    """
    now = today or _today_shanghai()
    first = now.replace(day=1)
    prev_month_last = first - timedelta(days=1)
    if now.day >= refresh_day:
        return prev_month_last.strftime("%Y-%m")
    earlier_last = prev_month_last.replace(day=1) - timedelta(days=1)
    return earlier_last.strftime("%Y-%m")


def should_skip_cn_macro(
    db: Session,
    *,
    refresh_day: int = CN_MACRO_REFRESH_DAY,
) -> bool:
    """水位已覆盖期望月份且上次成功、该 region 有数据时跳过外网。"""
    meta = get_sync_meta(db, _SYNC_TABLE)
    if not meta or not meta.last_synced_date:
        return False
    if meta.last_status != SyncStatus.SUCCESS:
        return False
    if count_macro_rows(db, REGION_CN) <= 0:
        return False
    expected = expected_cn_macro_period(refresh_day=refresh_day)
    return str(meta.last_synced_date) >= expected


def _latest_cpi_period(records: list[dict[str, Any]]) -> str | None:
    periods = [
        str(r["period"])
        for r in records
        if r.get("period") and r.get("metric") == METRIC_CPI_YOY and r.get("value") is not None
    ]
    return max(periods) if periods else None


def import_cn_macro(db: Session) -> dict[str, Any]:
    """拉取中国宏观月度指标并 upsert；尊重月频跳过窗口。"""
    start_ts = time.perf_counter()
    if should_skip_cn_macro(db):
        meta = get_sync_meta(db, _SYNC_TABLE)
        assert meta is not None
        total = count_macro_rows(db, REGION_CN)
        logger.info(
            "中国宏观刷新跳过: 已覆盖期望月份 (last_synced_date=%s expected=%s refresh_day=%s)",
            meta.last_synced_date,
            expected_cn_macro_period(),
            CN_MACRO_REFRESH_DAY,
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

    fr = fetch_cn_macro()
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
                "region": REGION_CN,
                "period": period,
                "metric": metric,
                "value": float(value),
                "cached_at": cached_at,
            }
        )

    if not records:
        error = fr.error_summary() or "中国宏观拉取失败"
        old_meta = get_sync_meta(db, _SYNC_TABLE)
        last_synced_at = upsert_sync_meta(
            db,
            _SYNC_TABLE,
            last_synced_date=old_meta.last_synced_date if old_meta else None,
            status=SyncStatus.FAILED,
            error=error,
        )
        result = build_result(
            imported=0,
            total=count_macro_rows(db, REGION_CN),
            last_date=old_meta.last_synced_date if old_meta else None,
            ok=False,
            source_errors=fr.to_error_map("cn_macro"),
            last_synced_at=last_synced_at,
        )
        return finalize_import_result(result, start_ts=start_ts, log_label="中国宏观刷新")

    imported = batch_upsert(db, MacroValue, records, _CONFLICT_COLS)
    latest = _latest_cpi_period(records)
    expected = expected_cn_macro_period()
    watermark = latest
    status = resolve_status(fr.ok, imported)
    if latest and latest < expected and status == SyncStatus.SUCCESS:
        status = SyncStatus.PARTIAL_FAILURE
        fr.errors.append(f"源端最新 CPI 月份 {latest} 尚未覆盖期望 {expected}")

    last_synced_at = upsert_sync_meta(
        db,
        _SYNC_TABLE,
        last_synced_date=watermark,
        status=status,
        error=fr.error_summary(),
    )
    result = build_result(
        imported=imported,
        total=count_macro_rows(db, REGION_CN),
        last_date=watermark,
        ok=status == SyncStatus.SUCCESS,
        source_errors=fr.to_error_map("cn_macro") if fr.errors else {},
        last_synced_at=last_synced_at,
    )
    result["status"] = status
    return finalize_import_result(result, start_ts=start_ts, log_label="中国宏观刷新")
