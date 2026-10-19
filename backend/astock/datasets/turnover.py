"""沪深两市成交额数据集。"""


import logging

import pandas as pd

from astock.config import EXCHANGE_TURNOVER_CODES, START_DATE
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.datasets.result import FetchResult
from astock.providers.baostock.client import (
    BaostockQueryError,
    baostock_session,
    login_error,
)
from astock.providers.baostock import market as bs_market

logger = logging.getLogger(__name__)


def fetch_turnover(start_date: str | None = None) -> FetchResult:
    start = start_date or START_DATE
    end = last_settled_date()
    errors: list[str] = []
    index_codes = EXCHANGE_TURNOVER_CODES

    try:
        with baostock_session() as lg:
            if err := login_error(lg):
                return FetchResult.failure(err)

            all_records: list[pd.DataFrame] = []
            for col_name, code in index_codes.items():
                try:
                    result = bs_market.query_exchange_amount(
                        code,
                        col_name=col_name,
                        start_date=start,
                        end_date=end,
                    )
                except (BaostockQueryError, RuntimeError) as e:
                    errors.append(str(e))
                    continue
                if result is not None:
                    all_records.append(result)

            if errors or len(all_records) < len(index_codes):
                if not errors:
                    errors.append("成交额一侧结果为空")
                return FetchResult(records=[], ok=False, errors=errors)

            grouped = (
                pd.concat(all_records, axis=0)
                .groupby("date", as_index=False)
                .sum(min_count=1)
            )
            # groupby.sum 的标注是标量 / Series / DataFrame 联合类型，收窄后 dropna 才对得上。
            if not isinstance(grouped, pd.DataFrame):
                return FetchResult.failure("成交额汇总结果不是表格")
            amount_cols = list(index_codes.keys())
            missing_cols = [col for col in amount_cols if col not in grouped.columns]
            if missing_cols:
                errors.append(f"成交额缺少列: {','.join(missing_cols)}")
                return FetchResult(records=[], ok=False, errors=errors)

            complete = grouped.dropna(subset=amount_cols)
            dropped = len(grouped) - len(complete)
            if dropped:
                errors.append(f"成交额 {dropped} 个交易日两市不齐，已丢弃")
            if complete.empty:
                if errors:
                    return FetchResult(records=[], ok=False, errors=errors)
                logger.info("成交额无新增数据: %s → %s", start, end)
                return FetchResult.empty()

            complete = complete.sort_values("date")
            complete["turnover"] = complete[amount_cols].sum(axis=1)
            cached_at = iso_now()
            records = [
                {
                    "date": row["date"],
                    "sse_amount": row["sse_amount"],
                    "szse_amount": row["szse_amount"],
                    "turnover": row["turnover"],
                    "cached_at": cached_at,
                }
                for row in complete.to_dict("records")
            ]
            logger.info("成交额拉取完成: %s 条 (%s → %s)", len(records), start, end)
            return FetchResult(records=records, ok=len(errors) == 0, errors=errors)
    except BaostockQueryError as e:
        return FetchResult.failure(str(e))
