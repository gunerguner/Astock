"""中行汇率抓取。"""

import logging
from datetime import timedelta

import akshare as ak
import pandas as pd

from astock.config import CN_INDEX_LOOKBACK_DAYS
from astock.core.datetime_utils import normalize_date, now_local
from astock.sources.market_overview._common import _retry_call, _tail_closes

logger = logging.getLogger(__name__)


def fetch_boc_forex(symbol: str, n: int) -> dict[str, float]:
    end = now_local()
    start = end - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
    try:
        df = _retry_call(
            f"currency_boc_sina:{symbol}",
            lambda: ak.currency_boc_sina(
                symbol=symbol,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            ),
        )
    except Exception as e:
        logger.warning("中行汇率 %s 抓取失败: %s", symbol, e)
        return {}
    if df is None or df.empty:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = normalize_date(row.get("日期"))
        mid = pd.to_numeric(row.get("央行中间价"), errors="coerce")
        if d and pd.notna(mid):
            pairs.append((d, float(mid) / 100.0))
    return _tail_closes(pairs, n)
