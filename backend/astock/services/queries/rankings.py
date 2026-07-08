"""成交额与个股排名查询。"""

from sqlmodel import Session, select

from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.schemas.analysis import (
    StockRankingItem,
    StockRankingResponse,
    TurnoverRankingItem,
    TurnoverRankingResponse,
)
from astock.services.queries._common import get_bull_market_period


def turnover_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> TurnoverRankingResponse:
    query = select(Turnover).order_by(Turnover.turnover.desc())
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


def stock_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> StockRankingResponse:
    query = select(StockTurnover).order_by(StockTurnover.amount.desc())
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
