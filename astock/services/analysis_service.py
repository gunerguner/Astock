"""分析服务：牛市区间统计（供后续查询 API 复用）。"""

import pandas as pd
from sqlmodel import Session, select

from astock.config import BULL_MARKETS
from astock.models.point import Point
from astock.models.turnover import Turnover


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
