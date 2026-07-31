"""外盘期货近期收盘价。"""


import logging

from astock.datasets.market_overview.common import tail_closes
from astock.providers.akshare.assets import fetch_commodity_history

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
    return tail_closes(pairs, n, market="us")
