"""美国宏观只读查询（长表 pivot 为宽格式响应）。"""

from __future__ import annotations

from sqlmodel import Session, col, select

from astock.config import US_MACRO_START_PERIOD
from astock.models.macro import (
    METRIC_CPI_YOY,
    METRIC_FED_RATE_UPPER,
    REGION_US,
    MacroValue,
)
from astock.schemas.analysis import UsMacroPointItem, UsMacroResponse
from astock.services.sync_store import get_sync_meta

_US_METRICS = (METRIC_CPI_YOY, METRIC_FED_RATE_UPPER)


def get_us_macro(
    db: Session,
    *,
    start: str = US_MACRO_START_PERIOD,
) -> UsMacroResponse:
    """按起始月份查询 CPI / 联邦基金利率月度序列。"""
    start_period = (start or US_MACRO_START_PERIOD).strip()[:7]
    rows = db.exec(
        select(MacroValue)
        .where(col(MacroValue.region) == REGION_US)
        .where(col(MacroValue.period) >= start_period)
        .where(col(MacroValue.metric).in_(_US_METRICS))
        .order_by(col(MacroValue.period), col(MacroValue.metric))
    ).all()

    by_period: dict[str, dict[str, float | None]] = {}
    for row in rows:
        bucket = by_period.setdefault(
            row.period,
            {
                METRIC_CPI_YOY: None,
                METRIC_FED_RATE_UPPER: None,
            },
        )
        bucket[row.metric] = row.value

    points = [
        UsMacroPointItem(
            period=period,
            cpi_yoy=vals[METRIC_CPI_YOY],
            fed_rate_upper=vals[METRIC_FED_RATE_UPPER],
        )
        for period, vals in sorted(by_period.items())
    ]
    # 与旧宽表合并一致：丢弃晚于最新 CPI 的纯利率月份
    cpi_periods = [p.period for p in points if p.cpi_yoy is not None]
    if cpi_periods:
        max_cpi = max(cpi_periods)
        points = [
            p for p in points if p.cpi_yoy is not None or p.period <= max_cpi
        ]
    latest = next(
        (p.period for p in reversed(points) if p.cpi_yoy is not None),
        points[-1].period if points else None,
    )

    meta = get_sync_meta(db, "us_macro")
    return UsMacroResponse(
        start=start_period,
        latest_period=latest,
        last_synced_at=meta.last_synced_at if meta else None,
        points=points,
    )
