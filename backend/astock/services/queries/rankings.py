"""成交额与个股排名查询。"""

from datetime import date

from sqlalchemy import func
from sqlmodel import Session, col, select

from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.schemas.analysis import (
    StockRankingItem,
    StockRankingResponse,
    TurnoverRankingItem,
    TurnoverRankingResponse,
    TurnoverSeriesItem,
    TurnoverSeriesResponse,
)
from astock.services.queries._common import get_bull_market_period

_SERIES_YEARS = {"1y": 1, "5y": 5}
_HISTORY_TOP = 20


def _shift_years(date_text: str, years: int) -> str:
    """按日历年回推；2 月 29 日落到非闰年时取 2 月 28 日。"""
    current = date.fromisoformat(date_text)
    try:
        shifted = current.replace(year=current.year - years)
    except ValueError:
        shifted = current.replace(year=current.year - years, month=2, day=28)
    return shifted.isoformat()


def turnover_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> TurnoverRankingResponse:
    query = select(Turnover).order_by(col(Turnover.turnover).desc())
    period = get_bull_market_period(bull_market)
    if period:
        query = query.where(Turnover.date >= period[0], Turnover.date <= period[1])
    rows = db.exec(query.limit(top)).all()
    items = [
        TurnoverRankingItem(
            rank=idx,
            date=row.date,
            sse_amount=row.sse_amount,
            szse_amount=row.szse_amount,
            turnover=row.turnover,
        )
        for idx, row in enumerate(rows, start=1)
    ]
    return TurnoverRankingResponse(
        top=top,
        bull_market=bull_market if bull_market and bull_market != "all" else None,
        items=items,
    )


def turnover_series(db: Session, *, series_range: str) -> TurnoverSeriesResponse:
    """日频两市成交额。1y/5y 相对库内最新交易日回推，all 返回全量。"""
    top_rows = db.exec(
        select(Turnover).order_by(col(Turnover.turnover).desc()).limit(_HISTORY_TOP)
    ).all()
    top_ranks = {row.date: rank for rank, row in enumerate(top_rows, start=1)}

    latest = db.exec(select(func.max(Turnover.date))).one()
    query = select(Turnover).order_by(col(Turnover.date).asc())
    years = _SERIES_YEARS.get(series_range)
    if years is not None and latest is not None:
        query = query.where(Turnover.date >= _shift_years(latest, years))

    items = [
        TurnoverSeriesItem(
            date=row.date,
            sse_amount=row.sse_amount,
            szse_amount=row.szse_amount,
            turnover=row.turnover,
            top_rank=top_ranks.get(row.date),
        )
        for row in db.exec(query).all()
    ]
    return TurnoverSeriesResponse(
        range=series_range,
        latest_date=latest,
        items=items,
    )


def stock_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> StockRankingResponse:
    query = select(StockTurnover).order_by(col(StockTurnover.amount).desc())
    period = get_bull_market_period(bull_market)
    if period:
        query = query.where(
            StockTurnover.date >= period[0], StockTurnover.date <= period[1]
        )
    rows = db.exec(query.limit(top)).all()
    items = [
        StockRankingItem(
            rank=idx,
            date=row.date,
            code=row.code,
            name=row.name,
            amount=row.amount,
        )
        for idx, row in enumerate(rows, start=1)
    ]
    return StockRankingResponse(
        top=top,
        bull_market=bull_market if bull_market and bull_market != "all" else None,
        items=items,
    )
