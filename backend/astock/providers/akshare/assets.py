"""akshare 全球资产原始查询：美股、贵金属、外盘期货。"""

from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

from astock.core.datetime_utils import normalize_date
from astock.providers._shared.retry import retry_call

logger = logging.getLogger(__name__)


def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = out["date"].map(normalize_date)
    for col in ("open", "high", "low", "close"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "close", "high"])
    out = out.sort_values("date").reset_index(drop=True)
    return out


def fetch_us_stock_daily(ticker: str) -> pd.DataFrame:
    """美股日线；新股无复权因子时回退未复权。"""
    try:
        df = ak.stock_us_daily(symbol=ticker, adjust="qfq")
    except ValueError as e:
        if "read-only" not in str(e):
            raise
        logger.warning(
            "%s 前复权计算失败(akshare 已知缺陷,新股无复权因子)，回退未复权数据",
            ticker,
        )
        df = ak.stock_us_daily(symbol=ticker, adjust="")
    return _normalize_history_df(df)


def fetch_commodity_history(code: str) -> pd.DataFrame:
    """外盘期货/贵金属历史。"""
    df = retry_call(
        f"futures_foreign_hist:{code}",
        lambda: ak.futures_foreign_hist(symbol=code),
    )
    return _normalize_history_df(df)


def fetch_asset_history(ticker: str, asset_type: str) -> pd.DataFrame:
    if asset_type == "stock":
        return fetch_us_stock_daily(ticker)
    return fetch_commodity_history(ticker)
