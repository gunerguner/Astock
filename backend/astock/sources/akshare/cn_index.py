"""akshare A 股指数日线。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import POINT_INDEX_CONFIG, START_DATE
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.retry import retry_call
from astock.sources.symbols import cn_index_sina_symbol

logger = logging.getLogger(__name__)


def fetch_cn_index_daily_raw(sina_symbol: str) -> pd.DataFrame:
    """拉取新浪 A 股指数日线原始 DataFrame（含 date/close）。"""
    return retry_call(
        f"stock_zh_index_daily:{sina_symbol}",
        lambda: ak.stock_zh_index_daily(symbol=sina_symbol),
    )


def fetch_cn_index_point(
    index_code: str, start_date: str | None = None
) -> SourceFetchResult:
    """通过 akshare（新浪）拉取 A 股指数日线收盘价，输出 DB 记录形状。"""
    if index_code not in POINT_INDEX_CONFIG:
        return SourceFetchResult.failure(f"未知指数代码: {index_code}")

    config = POINT_INDEX_CONFIG[index_code]
    index_name = str(config["name"])
    start = start_date or START_DATE
    end = last_settled_date()
    sina_symbol = cn_index_sina_symbol(index_code)

    try:
        raw = fetch_cn_index_daily_raw(sina_symbol)
    except Exception as e:
        msg = f"{index_name}点位查询失败(akshare): {e}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)

    if raw is None or raw.empty:
        logger.info("%s点位无新增数据(akshare): %s → %s", index_name, start, end)
        return SourceFetchResult.empty()

    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    if df.empty:
        logger.info("%s点位无有效数据(akshare): %s → %s", index_name, start, end)
        return SourceFetchResult.empty()

    cached_at = iso_now()
    records = [
        {
            "date": row["date"],
            "index_code": index_code,
            "close": float(row["close"]),
            "cached_at": cached_at,
        }
        for row in df.to_dict("records")
    ]
    logger.info(
        "%s点位拉取完成(akshare): %s 条 (%s → %s)",
        index_name,
        len(records),
        start,
        end,
    )
    return SourceFetchResult(records=records)
