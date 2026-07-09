"""中行汇率抓取。"""

import logging
from datetime import timedelta

import akshare as ak

from astock.config import CN_INDEX_LOOKBACK_DAYS
from astock.core.datetime_utils import now_local
from astock.sources.market_overview._common import df_to_tail_closes, safe_retry_df

logger = logging.getLogger(__name__)


def fetch_boc_forex(symbol: str, n: int) -> dict[str, float]:
    end = now_local()
    start = end - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
    df = safe_retry_df(
        f"currency_boc_sina:{symbol}",
        lambda: ak.currency_boc_sina(
            symbol=symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        ),
        logger=logger,
    )
    if df is None:
        return {}
    return df_to_tail_closes(
        df, n, date_col="日期", value_col="央行中间价", scale=0.01
    )
