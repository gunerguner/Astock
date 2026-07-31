"""个股代码清单与全市场日成交数据集。"""


from astock.datasets.result import FetchResult
from astock.providers.baostock import stocks as bs_stocks
from astock.providers.baostock.client import (
    BaostockQueryError,
    baostock_session,
    baostock_session_hold,
    login_error,
)

__all__ = [
    "baostock_session",
    "baostock_session_hold",
    "fetch_all_stock_codes_logged_in",
    "fetch_daily_astock_amounts_logged_in",
    "login_error",
]


def fetch_all_stock_codes_logged_in(as_of_date: str) -> FetchResult:
    try:
        records = bs_stocks.query_all_stock_codes(as_of_date)
    except BaostockQueryError as e:
        return FetchResult.failure(str(e))
    return FetchResult(records=records)


def fetch_daily_astock_amounts_logged_in(trade_date: str) -> FetchResult:
    try:
        records = bs_stocks.query_daily_astock_amounts(trade_date)
    except BaostockQueryError as e:
        return FetchResult.failure(str(e))
    if not records:
        return FetchResult.empty()
    return FetchResult(records=records)
