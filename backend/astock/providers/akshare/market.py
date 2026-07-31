"""akshare 市场原始查询：A 股指数、美股指数。"""


import logging

import akshare as ak
import pandas as pd

from astock.providers._shared.retry import retry_call, safe_retry_df

logger = logging.getLogger(__name__)


def fetch_cn_index_daily(sina_symbol: str) -> pd.DataFrame:
    """拉取新浪 A 股指数日线原始 DataFrame（含 date/close）。"""
    return retry_call(
        f"stock_zh_index_daily:{sina_symbol}",
        lambda: ak.stock_zh_index_daily(symbol=sina_symbol),
    )


def fetch_us_index_sina(symbol: str) -> pd.DataFrame | None:
    """新浪美股指数日线。"""
    return safe_retry_df(
        f"index_us_stock_sina:{symbol}",
        lambda: ak.index_us_stock_sina(symbol=symbol),
        logger_=logger,
    )


def fetch_usd_index_hist_em() -> pd.DataFrame | None:
    """东财全球指数历史：美元指数。"""
    try:
        df = ak.index_global_hist_em(symbol="美元指数")
    except Exception as e:
        logger.warning("美元指数 akshare 历史失败: %s", e)
        return None
    if df is None or df.empty or "日期" not in df.columns or "收盘" not in df.columns:
        return None
    return df
