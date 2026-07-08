"""A 股指数抓取。"""

import logging

import akshare as ak
import pandas as pd

from astock.sources.market_overview._common import (
    _cn_index_cutoff,
    _cn_index_sina_symbol,
    _tail_closes,
)

logger = logging.getLogger(__name__)


def fetch_cn_index(code: str, n: int) -> dict[str, float]:
    sina_symbol = _cn_index_sina_symbol(code)
    cutoff = _cn_index_cutoff()
    try:
        raw = ak.stock_zh_index_daily(symbol=sina_symbol)
    except Exception as e:
        logger.warning("A股指数 %s 抓取失败: %s", code, e)
        return {}
    if raw is None or raw.empty:
        return {}
    df = raw.rename(columns={"date": "Date", "close": "Close"})
    if "Date" not in df.columns or "Close" not in df.columns:
        return {}
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df[df["Close"].notna()]
    df = df[df.index >= pd.Timestamp(cutoff.date())]
    pairs = [(d.strftime("%Y-%m-%d"), float(row["Close"])) for d, row in df.iterrows()]
    return _tail_closes(pairs, n)
