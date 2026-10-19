"""baostock 市场数据原始查询：指数点位、交易所成交额。"""


import logging

import baostock as bs
import pandas as pd

from astock.providers.baostock.client import (
    BaostockQueryError,
    collect_rows,
    query_error,
    safe_baostock_call,
)

logger = logging.getLogger(__name__)


def query_index_closes(
    bs_code: str,
    *,
    start_date: str,
    end_date: str,
    label: str,
) -> pd.DataFrame:
    """查询指数日线收盘价，返回含 date/close 的 DataFrame。"""

    def _query() -> pd.DataFrame:
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,close",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
        )
        if rs is None:
            raise BaostockQueryError(f"{label}点位查询失败: 空结果")
        if err := query_error(f"{label}点位查询失败", rs):
            raise BaostockQueryError(err)
        rows = collect_rows(rs)
        if not rows:
            return pd.DataFrame(columns=["date", "close"])
        df = pd.DataFrame(rows, columns=rs.fields)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        cleaned = df.dropna(subset=["close"])
        if not isinstance(cleaned, pd.DataFrame):
            return pd.DataFrame(columns=["date", "close"])
        df = cleaned
        if df.empty:
            return pd.DataFrame(columns=["date", "close"])
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        selected = df.loc[:, ["date", "close"]]
        if not isinstance(selected, pd.DataFrame):
            return pd.DataFrame(columns=["date", "close"])
        return selected

    return safe_baostock_call(f"{label}点位查询超时/连接异常", _query)


def query_exchange_amount(
    code: str,
    *,
    col_name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame | None:
    """查询单一交易所成交额序列；无数据返回 None。"""

    def _fetch() -> pd.DataFrame | None:
        rs = bs.query_history_k_data_plus(
            code,
            "date,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
        )
        if rs is None:
            raise RuntimeError(f"{col_name} 查询失败: 空结果")
        if rs.error_code != "0":
            raise RuntimeError(f"{col_name} 查询失败: {rs.error_msg}")
        rows = collect_rows(rs)
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=rs.fields)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        cleaned = df.dropna(subset=["amount"])
        if not isinstance(cleaned, pd.DataFrame):
            return None
        df = cleaned
        if df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df.rename(columns={"amount": col_name}, inplace=True)
        selected = df.loc[:, ["date", col_name]]
        if not isinstance(selected, pd.DataFrame):
            return None
        return selected

    return safe_baostock_call(
        f"{col_name} 查询超时/连接异常",
        _fetch,
        log_level="warning",
    )
