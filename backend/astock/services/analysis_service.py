"""分析服务：牛市区间统计与排名查询。"""

from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import BULL_MARKETS
from astock.core.exceptions import AppError
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover


def _get_bull_market_period(bull_market: str | None) -> tuple[str, str] | None:
    if not bull_market or bull_market == "all":
        return None
    period = BULL_MARKETS.get(bull_market)
    if period is None:
        raise ValueError(f"未知牛市区间: {bull_market}")
    return period["start"], period["end"]


def build_bull_market_stats(
    db: Session,
    model: type,
    value_col_name: str,
    threshold: float,
) -> dict:
    value_col = getattr(model, value_col_name)
    items = []
    total_days = 0

    for market_name, period in BULL_MARKETS.items():
        count, max_value = db.exec(
            select(func.count(), func.max(value_col)).where(
                model.date >= period["start"],
                model.date <= period["end"],
                value_col > threshold,
            )
        ).one()
        days = int(count or 0)
        total_days += days
        items.append(
            {
                "market": market_name,
                "start": period["start"],
                "end": period["end"],
                "description": period.get("description"),
                "days": days,
                "max_value": float(max_value) if max_value is not None else None,
            }
        )

    items.sort(key=lambda x: x["end"], reverse=True)
    return {
        "threshold": threshold,
        "items": items,
        "total_days": total_days,
    }


def _require_rows(db: Session, model: type, empty_message: str) -> None:
    exists = db.exec(select(model).limit(1)).first()
    if exists is None:
        raise AppError(empty_message)


def bull_market_point_stats(db: Session, threshold: float) -> dict:
    _require_rows(db, Point, "上证点位数据为空，请先导入数据")
    return build_bull_market_stats(db, Point, "close", threshold)


def bull_market_turnover_stats(db: Session, threshold: float) -> dict:
    _require_rows(db, Turnover, "成交额数据为空，请先导入数据")
    return build_bull_market_stats(db, Turnover, "turnover", threshold)


def turnover_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> dict:
    query = select(Turnover).order_by(Turnover.turnover.desc())
    period = _get_bull_market_period(bull_market)
    if period:
        query = query.where(Turnover.date >= period[0], Turnover.date <= period[1])
    rows = db.exec(query.limit(top)).all()
    items = [
        {
            "rank": idx,
            "date": row.date,
            "sh_amount": row.sh_amount,
            "sz_amount": row.sz_amount,
            "turnover": row.turnover,
        }
        for idx, row in enumerate(rows, start=1)
    ]
    return {
        "top": top,
        "bull_market": bull_market if bull_market and bull_market != "all" else None,
        "items": items,
    }


def stock_ranking(
    db: Session, *, top: int = 20, bull_market: str | None = None
) -> dict:
    query = select(StockTurnover).order_by(StockTurnover.amount.desc())
    period = _get_bull_market_period(bull_market)
    if period:
        query = query.where(
            StockTurnover.date >= period[0], StockTurnover.date <= period[1]
        )
    rows = db.exec(query.limit(top)).all()
    items = [
        {
            "rank": idx,
            "date": row.date,
            "code": row.code,
            "name": row.name,
            "amount": row.amount,
        }
        for idx, row in enumerate(rows, start=1)
    ]
    return {
        "top": top,
        "bull_market": bull_market if bull_market and bull_market != "all" else None,
        "items": items,
    }

