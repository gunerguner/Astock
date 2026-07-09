"""美债收益率抓取。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import MARKET_OVERVIEW_RECENT_DAYS, US_BOND_COLUMNS
from astock.core.datetime_utils import normalize_date
from astock.sources.market_overview._common import _tail_closes
from astock.sources.retry import retry_call

logger = logging.getLogger(__name__)


def fetch_us_bond_rates() -> dict[str, dict[str, float]]:
    """一次调用返回 5/10/30 年美债 recent_closes。"""
    try:
        df = retry_call("bond_zh_us_rate", ak.bond_zh_us_rate)
    except Exception as e:
        logger.warning("美债收益率抓取失败: %s", e)
        return {}
    if df is None or df.empty:
        return {}

    result: dict[str, dict[str, float]] = {}
    for code, col in US_BOND_COLUMNS.items():
        pairs: list[tuple[str, float]] = []
        for _, row in df.iterrows():
            d = normalize_date(row.get("日期"))
            val = pd.to_numeric(row.get(col), errors="coerce")
            if d and pd.notna(val):
                pairs.append((d, float(val)))
        closes = _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS)
        if closes:
            result[code] = closes
    return result
