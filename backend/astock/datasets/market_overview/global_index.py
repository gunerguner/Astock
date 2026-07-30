"""全球指数近期收盘价。"""

from __future__ import annotations

import logging

from astock.config import GLOBAL_INDEX_SINA_FALLBACK
from astock.datasets.market_overview.common import df_to_tail_closes
from astock.datasets.market_overview.usd_index import fetch_usd_index
from astock.providers.akshare.market import fetch_us_index_sina

logger = logging.getLogger(__name__)

_GLOBAL_INDEX_EM_ONLY = {"美元指数"}


def fetch_global_index(symbol: str, n: int) -> dict[str, float]:
    sina_symbol = GLOBAL_INDEX_SINA_FALLBACK.get(symbol)
    if sina_symbol:
        df = fetch_us_index_sina(sina_symbol)
        if df is None:
            return {}
        return df_to_tail_closes(df, n, date_col="date", value_col="close", market="us")

    if symbol in _GLOBAL_INDEX_EM_ONLY:
        return fetch_usd_index(n)

    logger.warning("未知全球指数: %s", symbol)
    return {}
