"""baostock 沪深交易所全市场成交额抓取。"""

import logging

import baostock as bs
import pandas as pd

from astock.config import EXCHANGE_TURNOVER_CODES, START_DATE
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.sources.baostock.session import (
    collect_rows,
    login_failure,
    safe_baostock_call,
    baostock_session,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def fetch_turnover(start_date: str | None = None) -> SourceFetchResult:
    start = start_date or START_DATE
    end = last_settled_date()
    errors: list[str] = []

    index_codes = EXCHANGE_TURNOVER_CODES

    with baostock_session() as lg:
        if failed := login_failure(lg):
            return failed

        all_records: list[pd.DataFrame] = []
        for col_name, code in index_codes.items():
            def _fetch_one(col_name=col_name, code=code) -> pd.DataFrame | None:
                rs = bs.query_history_k_data_plus(
                    code,
                    "date,amount",
                    start_date=start,
                    end_date=end,
                    frequency="d",
                )
                if rs.error_code != "0":
                    raise RuntimeError(f"{col_name} 查询失败: {rs.error_msg}")
                rows = collect_rows(rs)
                if not rows:
                    return None
                df = pd.DataFrame(rows, columns=rs.fields)
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
                df = df.dropna(subset=["amount"])
                if df.empty:
                    return None
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                df.rename(columns={"amount": col_name}, inplace=True)
                return df[["date", col_name]]

            result = safe_baostock_call(
                f"{col_name} 查询超时/连接异常",
                _fetch_one,
                log_level="warning",
            )
            if isinstance(result, SourceFetchResult):
                errors.append(result.errors[0])
                continue
            if result is not None:
                all_records.append(result)

        if not all_records:
            if errors:
                return SourceFetchResult(records=[], ok=False, errors=errors)
            logger.info("成交额无新增数据: %s → %s", start, end)
            return SourceFetchResult.empty()

        merged = pd.concat(all_records, axis=0).groupby("date", as_index=False).sum()
        for col in index_codes:
            if col not in merged.columns:
                merged[col] = 0.0

        merged["turnover"] = merged[list(index_codes.keys())].sum(axis=1)
        merged = merged.sort_values("date")

        cached_at = iso_now()
        records = [
            {
                "date": row["date"],
                "sse_amount": row["sse_amount"],
                "szse_amount": row["szse_amount"],
                "turnover": row["turnover"],
                "cached_at": cached_at,
            }
            for row in merged.to_dict("records")
        ]
        logger.info("成交额拉取完成: %s 条 (%s → %s)", len(records), start, end)
        return SourceFetchResult(records=records, ok=len(errors) == 0, errors=errors)
