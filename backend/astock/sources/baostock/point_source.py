"""baostock 指数点位抓取。"""

import logging

import baostock as bs
import pandas as pd

from astock.config import POINT_INDEX_CONFIG, START_DATE
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.sources.baostock.session import (
    collect_rows,
    login_failure,
    query_failure,
    safe_baostock_call,
    baostock_session,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def fetch_point(
    index_code: str = "000001", start_date: str | None = None
) -> SourceFetchResult:
    if index_code not in POINT_INDEX_CONFIG:
        return SourceFetchResult.failure(f"未知指数代码: {index_code}")

    config = POINT_INDEX_CONFIG[index_code]
    if config.get("source") == "akshare":
        return SourceFetchResult.failure(
            f"指数 {index_code} 应通过 akshare 抓取，非 baostock"
        )

    bs_code = str(config["baostock_code"])
    index_name = str(config["name"])
    start = start_date or START_DATE
    end = last_settled_date()

    with baostock_session() as lg:
        if failed := login_failure(lg):
            return failed

        def _query() -> SourceFetchResult:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,close",
                start_date=start,
                end_date=end,
                frequency="d",
            )
            if failed := query_failure(f"{index_name}点位查询失败", rs):
                return failed
            rows = collect_rows(rs)
            if not rows:
                logger.info("%s点位无新增数据: %s → %s", index_name, start, end)
                return SourceFetchResult.empty()

            df = pd.DataFrame(rows, columns=rs.fields)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["close"])
            if df.empty:
                logger.info("%s点位无有效数据: %s → %s", index_name, start, end)
                return SourceFetchResult.empty()
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

            cached_at = iso_now()
            records = [
                {
                    "date": row["date"],
                    "index_code": index_code,
                    "close": row["close"],
                    "cached_at": cached_at,
                }
                for row in df.to_dict("records")
            ]
            logger.info(
                "%s点位拉取完成: %s 条 (%s → %s)",
                index_name,
                len(records),
                start,
                end,
            )
            return SourceFetchResult(records=records)

        result = safe_baostock_call(f"{index_name}点位查询超时/连接异常", _query)
        if isinstance(result, SourceFetchResult):
            return result
        return result
