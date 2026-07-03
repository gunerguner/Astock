"""分析逻辑：基于牛市区间对行情数据进行统计。"""

import pandas as pd

from .config import BULL_MARKETS


def analyze_bull_markets(df: pd.DataFrame, value_col: str, threshold: float) -> dict:
    """通用牛市时期统计"""
    results = {}

    for market_name, period in BULL_MARKETS.items():
        start_date = pd.to_datetime(period['start'])
        end_date = pd.to_datetime(period['end'])

        mask = (df['date'] >= start_date) & (df['date'] <= end_date) & (df[value_col] > threshold)
        period_data = df[mask]

        results[market_name] = {
            'days': len(period_data),
            'max_value': period_data[value_col].max() if len(period_data) > 0 else None
        }

    return results
