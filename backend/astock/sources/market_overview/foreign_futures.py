"""外盘期货抓取（复用 akshare.global_asset 底层）。"""

import logging

from astock.sources.akshare.global_asset import fetch_commodity_history
from astock.sources.market_overview._common import _tail_closes

logger = logging.getLogger(__name__)


def fetch_foreign_futures(code: str, n: int) -> dict[str, float]:
    try:
        df = fetch_commodity_history(code)
    except Exception as e:
        logger.warning("外盘期货 %s 抓取失败: %s", code, e)
        return {}
    if df.empty:
        return {}
    pairs = [(str(row["date"]), float(row["close"])) for _, row in df.iterrows()]
    return _tail_closes(pairs, n, market="us")
