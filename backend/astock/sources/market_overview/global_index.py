"""全球指数抓取。"""

import logging

import akshare as ak

from astock.config import GLOBAL_INDEX_SINA_FALLBACK
from astock.sources.market_overview._common import df_to_tail_closes, safe_retry_df
from astock.sources.market_overview.usd_index import fetch_usd_index

logger = logging.getLogger(__name__)

_GLOBAL_INDEX_EM_ONLY = {"美元指数"}


def _fetch_us_index_sina(symbol: str, n: int) -> dict[str, float]:
    df = safe_retry_df(
        f"index_us_stock_sina:{symbol}",
        lambda: ak.index_us_stock_sina(symbol=symbol),
        logger=logger,
    )
    if df is None:
        return {}
    return df_to_tail_closes(df, n, date_col="date", value_col="close", market="us")


def fetch_global_index(symbol: str, n: int) -> dict[str, float]:
    sina_symbol = GLOBAL_INDEX_SINA_FALLBACK.get(symbol)
    if sina_symbol:
        return _fetch_us_index_sina(sina_symbol, n)

    if symbol in _GLOBAL_INDEX_EM_ONLY:
        return fetch_usd_index(n)

    logger.warning("未知全球指数: %s", symbol)
    return {}
