"""美债收益率抓取。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import MARKET_OVERVIEW_RECENT_DAYS
from astock.core.datetime_utils import normalize_date
from astock.sources.market_overview._common import _retry_call, _tail_closes

logger = logging.getLogger(__name__)

_US_BOND_COLUMN_MAP = {
    "us_bond_5y": "美国国债收益率5年",
    "us_bond_10y": "美国国债收益率10年",
    "us_bond_30y": "美国国债收益率30年",
}


def fetch_us_bond_rates() -> dict[str, dict[str, float]]:
    """一次调用返回 5/10/30 年美债 recent_closes。"""
    try:
        df = _retry_call("bond_zh_us_rate", ak.bond_zh_us_rate)
    except Exception as e:
        logger.warning("美债收益率抓取失败: %s", e)
        return {}
    if df is None or df.empty:
        return {}

    result: dict[str, dict[str, float]] = {}
    for code, col in _US_BOND_COLUMN_MAP.items():
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
