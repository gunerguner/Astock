"""中国宏观只读查询（长表 pivot 为宽格式响应）。"""

from __future__ import annotations

from sqlmodel import Session, col, select

from astock.config import CN_MACRO_START_PERIOD
from astock.models.macro import (
    METRIC_CONSUMER_CONFIDENCE,
    METRIC_CPI_YOY,
    METRIC_PMI_MFG,
    METRIC_PMI_NON_MFG,
    METRIC_PPI_YOY,
    REGION_CN,
    MacroValue,
)
from astock.schemas.analysis import CnMacroPointItem, CnMacroResponse
from astock.services.sync_store import get_sync_meta

_CN_METRICS = (
    METRIC_CPI_YOY,
    METRIC_PPI_YOY,
    METRIC_PMI_MFG,
    METRIC_PMI_NON_MFG,
    METRIC_CONSUMER_CONFIDENCE,
)


def get_cn_macro(
    db: Session,
    *,
    start: str = CN_MACRO_START_PERIOD,
) -> CnMacroResponse:
    """按起始月份查询中国宏观月度序列。"""
    start_period = (start or CN_MACRO_START_PERIOD).strip()[:7]
    rows = db.exec(
        select(MacroValue)
        .where(col(MacroValue.region) == REGION_CN)
        .where(col(MacroValue.period) >= start_period)
        .where(col(MacroValue.metric).in_(_CN_METRICS))
        .order_by(col(MacroValue.period), col(MacroValue.metric))
    ).all()

    by_period: dict[str, dict[str, float | None]] = {}
    for row in rows:
        bucket = by_period.setdefault(
            row.period,
            {
                METRIC_CPI_YOY: None,
                METRIC_PPI_YOY: None,
                METRIC_PMI_MFG: None,
                METRIC_PMI_NON_MFG: None,
                METRIC_CONSUMER_CONFIDENCE: None,
            },
        )
        bucket[row.metric] = row.value

    points = [
        CnMacroPointItem(
            period=period,
            cpi_yoy=vals[METRIC_CPI_YOY],
            ppi_yoy=vals[METRIC_PPI_YOY],
            pmi_manufacturing=vals[METRIC_PMI_MFG],
            pmi_non_manufacturing=vals[METRIC_PMI_NON_MFG],
            consumer_confidence=vals[METRIC_CONSUMER_CONFIDENCE],
        )
        for period, vals in sorted(by_period.items())
    ]
    latest = next(
        (
            p.period
            for p in reversed(points)
            if any(
                v is not None
                for v in (
                    p.cpi_yoy,
                    p.ppi_yoy,
                    p.pmi_manufacturing,
                    p.pmi_non_manufacturing,
                    p.consumer_confidence,
                )
            )
        ),
        points[-1].period if points else None,
    )

    meta = get_sync_meta(db, "cn_macro")
    return CnMacroResponse(
        start=start_period,
        latest_period=latest,
        last_synced_at=meta.last_synced_at if meta else None,
        points=points,
    )
