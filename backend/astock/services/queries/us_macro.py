"""美国宏观只读查询（长表 pivot 为宽格式响应）。"""


from sqlmodel import Session

from astock.config import US_MACRO_START_PERIOD
from astock.datasets.macro.types import MacroMetric
from astock.schemas.analysis import UsMacroPointItem, UsMacroResponse
from astock.services.queries._common import (
    latest_period_with,
    load_macro_rows,
    pivot_macro_rows,
)
from astock.services.sync.store import get_sync_meta

_US_METRICS: tuple[MacroMetric, ...] = ("cpi_yoy", "fed_rate_upper")


def get_us_macro(
    db: Session,
    *,
    start: str = US_MACRO_START_PERIOD,
) -> UsMacroResponse:
    """按起始月份查询 CPI / 联邦基金利率月度序列。"""
    start_period = (start or US_MACRO_START_PERIOD).strip()[:7]
    rows = load_macro_rows(
        db, region="us", metrics=_US_METRICS, start_period=start_period
    )
    by_period = pivot_macro_rows(rows, _US_METRICS)
    points = [
        UsMacroPointItem(
            period=period,
            cpi_yoy=vals["cpi_yoy"],
            fed_rate_upper=vals["fed_rate_upper"],
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
    latest = latest_period_with(
        points,
        predicate=lambda p: p.cpi_yoy is not None,
    )

    meta = get_sync_meta(db, "us_macro")
    return UsMacroResponse(
        start=start_period,
        latest_period=latest,
        last_synced_at=meta.last_synced_at if meta else None,
        points=points,
    )
