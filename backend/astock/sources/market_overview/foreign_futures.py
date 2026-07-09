"""外盘期货抓取。"""

import logging

import akshare as ak
import pandas as pd

from astock.core.datetime_utils import normalize_date
from astock.sources.market_overview._common import _retry_call, _tail_closes

logger = logging.getLogger(__name__)


def fetch_foreign_futures(code: str, n: int) -> dict[str, float]:
    try:
        df = _retry_call(f"futures_foreign:{code}", lambda: ak.futures_foreign_hist(symbol=code))
    except Exception as e:
        logger.warning("外盘期货 %s 抓取失败: %s", code, e)
        return {}
    if df is None or df.empty or "date" not in df.columns or "close" not in df.columns:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = normalize_date(row["date"])
        close = pd.to_numeric(row["close"], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return _tail_closes(pairs, n, market="us")
