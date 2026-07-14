"""美债收益率抓取。"""

import logging

import akshare as ak

from astock.config import MARKET_OVERVIEW_RECENT_DAYS, US_BOND_COLUMNS
from astock.sources.market_overview._common import df_to_tail_closes, safe_retry_df

logger = logging.getLogger(__name__)


def fetch_us_bond_rates() -> dict[str, dict[str, float]]:
    """一次调用返回配置中的中美国债 recent_closes。"""
    df = safe_retry_df("bond_zh_us_rate", ak.bond_zh_us_rate, logger=logger)
    if df is None:
        return {}

    result: dict[str, dict[str, float]] = {}
    for code, col in US_BOND_COLUMNS.items():
        closes = df_to_tail_closes(
            df, MARKET_OVERVIEW_RECENT_DAYS, date_col="日期", value_col=col
        )
        if closes:
            result[code] = closes
    return result
