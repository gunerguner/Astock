"""沪深两市成交额数据集。"""

from __future__ import annotations

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

            if not all_records:
                if errors:
                    return FetchResult(records=[], ok=False, errors=errors)
                logger.info("成交额无新增数据: %s → %s", start, end)
                return FetchResult.empty()

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
            return FetchResult(records=records, ok=len(errors) == 0, errors=errors)
    except BaostockQueryError as e:
        return FetchResult.failure(str(e))
