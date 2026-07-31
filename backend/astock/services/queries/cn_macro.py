"""中国宏观只读查询（长表 pivot 为宽格式响应）。"""


from sqlmodel import Session

from astock.config import CN_MACRO_START_PERIOD
from astock.datasets.macro.types import MacroMetric
from astock.schemas.analysis import CnMacroPointItem, CnMacroResponse
from astock.services.queries._common import (
    latest_period_with,
    load_macro_rows,
    pivot_macro_rows,
)
from astock.services.sync.store import get_sync_meta

_CN_METRICS: tuple[MacroMetric, ...] = (
    "cpi_yoy",
    "ppi_yoy",
    "pmi_manufacturing",
    "pmi_non_manufacturing",
    "consumer_confidence",
)


def get_cn_macro(
    db: Session,
    *,
    start: str = CN_MACRO_START_PERIOD,
) -> CnMacroResponse:
    """按起始月份查询中国宏观月度序列。"""
    start_period = (start or CN_MACRO_START_PERIOD).strip()[:7]
    rows = load_macro_rows(
        db, region="cn", metrics=_CN_METRICS, start_period=start_period
    )
    by_period = pivot_macro_rows(rows, _CN_METRICS)
    points = [
        CnMacroPointItem(
            period=period,
            cpi_yoy=vals["cpi_yoy"],
            ppi_yoy=vals["ppi_yoy"],
            pmi_manufacturing=vals["pmi_manufacturing"],
            pmi_non_manufacturing=vals["pmi_non_manufacturing"],
            consumer_confidence=vals["consumer_confidence"],
        )
        for period, vals in sorted(by_period.items())
    ]
    latest = latest_period_with(
        points,
        predicate=lambda p: any(
            v is not None
            for v in (
                p.cpi_yoy,
                p.ppi_yoy,
                p.pmi_manufacturing,
                p.pmi_non_manufacturing,
                p.consumer_confidence,
            )
        ),
    )

    meta = get_sync_meta(db, "cn_macro")
    return CnMacroResponse(
        start=start_period,
        latest_period=latest,
        last_synced_at=meta.last_synced_at if meta else None,
        points=points,
    )
