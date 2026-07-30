"""中行汇率近期收盘价。"""

from __future__ import annotations

from datetime import timedelta

from astock.config import CN_INDEX_LOOKBACK_DAYS
from astock.core.datetime_utils import now_local
from astock.datasets.market_overview.common import df_to_tail_closes
from astock.providers.akshare.economics import fetch_boc_forex as provider_boc_forex


def fetch_boc_forex(symbol: str, n: int) -> dict[str, float]:
    end = now_local()
    start = end - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
    df = provider_boc_forex(
        symbol,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )
    if df is None:
        return {}
    return df_to_tail_closes(
        df, n, date_col="日期", value_col="央行中间价", scale=0.01
    )
