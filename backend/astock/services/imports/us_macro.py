"""美国宏观数据导入（月频 + sync_meta）。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session

from astock.config import US_MACRO_REFRESH_DAY, US_MACRO_START_PERIOD
from astock.core.datetime_utils import iso_now
from astock.core.sync_status import SyncStatus
from astock.models.us_macro import UsMacroPoint
from astock.services.imports._common import (
    build_result,
    finalize_import_result,
    resolve_status,
)
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.sources.us_macro import fetch_us_macro

logger = logging.getLogger(__name__)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SYNC_TABLE = "us_macro"


def _today_shanghai() -> date:
    return datetime.now(_SHANGHAI).date()


def expected_us_macro_period(
    today: date | None = None,
    *,
    refresh_day: int = US_MACRO_REFRESH_DAY,
) -> str:
    """北京时间下当前应覆盖的最新 CPI 月份。

    - 每月 refresh_day（含）之后：期望上月已发布
    - 此前：仅期望上上月（上月 CPI 通常尚未稳定发布）
    """
    now = today or _today_shanghai()
    first = now.replace(day=1)
    prev_month_last = first - timedelta(days=1)
    if now.day >= refresh_day:
        return prev_month_last.strftime("%Y-%m")
    earlier_last = prev_month_last.replace(day=1) - timedelta(days=1)
    return earlier_last.strftime("%Y-%m")


def should_skip_us_macro(
    db: Session,
    *,
    refresh_day: int = US_MACRO_REFRESH_DAY,
) -> bool:
    """水位已覆盖期望月份且上次成功、表非空时跳过外网。"""
    meta = get_sync_meta(db, _SYNC_TABLE)
    if not meta or not meta.last_synced_date:
        return False
    if meta.last_status != SyncStatus.SUCCESS:
        return False
    if count_rows(db, UsMacroPoint) <= 0:
        return False
    expected = expected_us_macro_period(refresh_day=refresh_day)
    # last_synced_date 存 YYYY-MM
    return str(meta.last_synced_date) >= expected


def _latest_cpi_period(records: list[dict[str, Any]]) -> str | None:
    periods = [
        str(r["period"])
        for r in records
        if r.get("period") and r.get("cpi_yoy") is not None
    ]
    return max(periods) if periods else None


def import_us_macro(db: Session) -> dict[str, Any]:
    """拉取美国宏观月度序列并 upsert；尊重月频跳过窗口。"""
    start_ts = time.perf_counter()
    if should_skip_us_macro(db):
        meta = get_sync_meta(db, _SYNC_TABLE)
        assert meta is not None
        total = count_rows(db, UsMacroPoint)
        logger.info(
            "美国宏观刷新跳过: 已覆盖期望月份 (last_synced_date=%s expected=%s refresh_day=%s)",
            meta.last_synced_date,
            expected_us_macro_period(),
            US_MACRO_REFRESH_DAY,
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

    fr = fetch_us_macro()
    cached_at = iso_now()
    records: list[dict[str, Any]] = []
    for row in fr.records:
        period = str(row.get("period") or "")
        if not period or period < US_MACRO_START_PERIOD:
            # 仍入库更早历史，便于以后扩展；水位与 API 默认展示从 START 起
            # 这里选择：全量入库所有有效月，API 再按 start 过滤
            pass
        if not period:
            continue
        records.append(
            {
                "period": period,
                "cpi_yoy": row.get("cpi_yoy"),
                "fed_rate_upper": row.get("fed_rate_upper"),
                "cached_at": cached_at,
            }
        )

    # 双源全失败：保留旧库，不推进水位日期
    if not records:
        error = fr.error_summary() or "美国宏观拉取失败"
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
            total=count_rows(db, UsMacroPoint),
            last_date=old_meta.last_synced_date if old_meta else None,
            ok=False,
            source_errors=fr.to_error_map("us_macro"),
            last_synced_at=last_synced_at,
        )
        return finalize_import_result(result, start_ts=start_ts, log_label="美国宏观刷新")

    imported = batch_upsert(db, UsMacroPoint, records, ["period"])
    latest = _latest_cpi_period(records)
    expected = expected_us_macro_period()
    # 源端尚未发布期望月：不推进到 expected，保留实际最新月，下次继续重试
    watermark = latest
    status = resolve_status(fr.ok, imported)
    # 有数据入库但未达期望月 → partial（提醒源端滞后），仍记成功水位为实际 latest
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
        total=count_rows(db, UsMacroPoint),
        last_date=watermark,
        ok=status == SyncStatus.SUCCESS,
        source_errors=fr.to_error_map("us_macro") if fr.errors else {},
        last_synced_at=last_synced_at,
    )
    # build_result 用 ok 推断 status；上面 partial 需回写
    result["status"] = status
    return finalize_import_result(result, start_ts=start_ts, log_label="美国宏观刷新")
