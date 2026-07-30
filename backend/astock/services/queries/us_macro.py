"""美国宏观只读查询。"""

from __future__ import annotations

from sqlmodel import Session, col, select

from astock.config import US_MACRO_START_PERIOD
from astock.models.us_macro import UsMacroPoint
from astock.schemas.analysis import UsMacroPointItem, UsMacroResponse
from astock.services.sync_store import get_sync_meta


def get_us_macro(
    db: Session,
    *,
    start: str = US_MACRO_START_PERIOD,
) -> UsMacroResponse:
    """按起始月份查询 CPI / 联邦基金利率月度序列。"""
    start_period = (start or US_MACRO_START_PERIOD).strip()[:7]
    rows = db.exec(
        select(UsMacroPoint)
        .where(col(UsMacroPoint.period) >= start_period)
        .order_by(col(UsMacroPoint.period))
    ).all()

    points = [
        UsMacroPointItem(
            period=row.period,
            cpi_yoy=row.cpi_yoy,
            fed_rate_upper=row.fed_rate_upper,
        )
        for row in rows
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
