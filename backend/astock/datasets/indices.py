"""指数点位数据集：按配置选择 baostock / akshare。"""

from __future__ import annotations

import logging

import pandas as pd

from astock.config import POINT_INDEX_CONFIG, START_DATE
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.datasets.result import FetchResult
from astock.providers._shared.symbols import cn_index_sina_symbol
from astock.providers.akshare import market as ak_market
from astock.providers.baostock.client import (
    BaostockQueryError,
    baostock_session,
    login_error,
)
from astock.providers.baostock import market as bs_market

logger = logging.getLogger(__name__)


def _records_from_closes(
    df: pd.DataFrame,
    *,
    index_code: str,
    start: str,
    end: str,
) -> list[dict]:
    if df is None or df.empty:
        return []
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"])
    out = out[(out["date"] >= start) & (out["date"] <= end)]
    if out.empty:
        return []
    cached_at = iso_now()
    return [
        {
            "date": row["date"],
            "index_code": index_code,
            "close": float(row["close"]),
            "cached_at": cached_at,
        }
        for row in out.to_dict("records")
    ]


def _fetch_baostock(index_code: str, start: str, end: str, index_name: str) -> FetchResult:
    config = POINT_INDEX_CONFIG[index_code]
    bs_code = str(config["baostock_code"])
    try:
        with baostock_session() as lg:
            if err := login_error(lg):
                return FetchResult.failure(err)
            df = bs_market.query_index_closes(
                bs_code, start_date=start, end_date=end, label=index_name
            )
    except BaostockQueryError as e:
        return FetchResult.failure(str(e))

    records = _records_from_closes(df, index_code=index_code, start=start, end=end)
    if not records:
        logger.info("%s点位无新增数据: %s → %s", index_name, start, end)
        return FetchResult.empty()
    logger.info("%s点位拉取完成: %s 条 (%s → %s)", index_name, len(records), start, end)
    return FetchResult(records=records)


def _fetch_akshare(index_code: str, start: str, end: str, index_name: str) -> FetchResult:
    sina_symbol = cn_index_sina_symbol(index_code)
    try:
        raw = ak_market.fetch_cn_index_daily(sina_symbol)
    except Exception as e:
        msg = f"{index_name}点位查询失败(akshare): {e}"
        logger.error(msg)
        return FetchResult.failure(msg)

    if raw is None or raw.empty:
        logger.info("%s点位无新增数据(akshare): %s → %s", index_name, start, end)
        return FetchResult.empty()

    records = _records_from_closes(raw, index_code=index_code, start=start, end=end)
    if not records:
        logger.info("%s点位无有效数据(akshare): %s → %s", index_name, start, end)
        return FetchResult.empty()
    logger.info(
        "%s点位拉取完成(akshare): %s 条 (%s → %s)",
        index_name,
        len(records),
        start,
        end,
    )
    return FetchResult(records=records)


def fetch_point(
    index_code: str = "000001", start_date: str | None = None
) -> FetchResult:
    """按 POINT_INDEX_CONFIG[index_code].source 选择供应商。"""
    if index_code not in POINT_INDEX_CONFIG:
        return FetchResult.failure(f"未知指数代码: {index_code}")

    config = POINT_INDEX_CONFIG[index_code]
    index_name = str(config["name"])
    start = start_date or START_DATE
    end = last_settled_date()
    source = str(config.get("source", "baostock"))

    if source == "akshare":
        return _fetch_akshare(index_code, start, end, index_name)
    return _fetch_baostock(index_code, start, end, index_name)
