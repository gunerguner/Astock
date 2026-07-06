"""分析服务：牛市区间统计与排名查询。"""

import pandas as pd
from sqlmodel import Session, select

from astock.config import BULL_MARKETS
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


def analyze_bull_markets(df: pd.DataFrame, value_col: str, threshold: float) -> dict:
    results = {}
    for market_name, period in BULL_MARKETS.items():
        start_date = pd.to_datetime(period["start"])
        end_date = pd.to_datetime(period["end"])
        mask = (
            (df["date"] >= start_date)
            & (df["date"] <= end_date)
            & (df[value_col] > threshold)
        )
        period_data = df[mask]
        results[market_name] = {
            "days": len(period_data),
            "max_value": period_data[value_col].max() if len(period_data) > 0 else None,
        }
    return results


def build_bull_market_stats(
    df: pd.DataFrame, value_col: str, threshold: float
) -> dict:
    raw = analyze_bull_markets(df, value_col, threshold)
    items = []
    for market_name, period in BULL_MARKETS.items():
        info = raw[market_name]
        items.append(
            {
                "market": market_name,
                "start": period["start"],
                "end": period["end"],
                "description": period.get("description"),
                "days": info["days"],
                "max_value": info["max_value"],
            }
        )
    items.sort(key=lambda x: x["end"], reverse=True)
    return {
        "threshold": threshold,
        "items": items,
        "total_days": sum(item["days"] for item in items),
    }


def get_turnover_dataframe(db: Session) -> pd.DataFrame:
    rows = db.exec(select(Turnover).order_by(Turnover.date)).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([row.model_dump() for row in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_point_dataframe(db: Session) -> pd.DataFrame:
    rows = db.exec(select(Point).order_by(Point.date)).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([row.model_dump() for row in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df


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


def get_bull_markets_meta() -> dict:
    items = [
        {
            "name": name,
            "start": period["start"],
            "end": period["end"],
            "description": period.get("description"),
        }
        for name, period in BULL_MARKETS.items()
    ]
    items.sort(key=lambda x: x["end"], reverse=True)
    return {"items": items}
