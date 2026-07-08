"""全球指数抓取。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import GLOBAL_INDEX_SINA_FALLBACK
from astock.core.datetime_utils import normalize_date
from astock.sources.market_overview._common import _retry_call, _tail_closes
from astock.sources.market_overview.usd_index import fetch_usd_index

logger = logging.getLogger(__name__)

_GLOBAL_INDEX_EM_ONLY = {"美元指数"}


def _fetch_us_index_sina(symbol: str, n: int) -> dict[str, float]:
    try:
        df = _retry_call(f"index_us_stock_sina:{symbol}", lambda: ak.index_us_stock_sina(symbol=symbol))
    except Exception as e:
        logger.warning("新浪美股指数 %s 失败: %s", symbol, e)
        return {}
    if df is None or df.empty:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = normalize_date(row.get("date"))
        close = pd.to_numeric(row.get("close"), errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return _tail_closes(pairs, n)


def fetch_global_index(symbol: str, n: int) -> dict[str, float]:
    sina_symbol = GLOBAL_INDEX_SINA_FALLBACK.get(symbol)
    if sina_symbol:
        return _fetch_us_index_sina(sina_symbol, n)

    if symbol in _GLOBAL_INDEX_EM_ONLY:
        return fetch_usd_index(n)

    logger.warning("未知全球指数: %s", symbol)
    return {}
