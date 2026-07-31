"""akshare 宏观/债券/汇率原始查询。"""


import logging

import akshare as ak
import pandas as pd

from astock.providers._shared.retry import safe_retry_df

logger = logging.getLogger(__name__)


def fetch_china_cpi() -> pd.DataFrame | None:
    return safe_retry_df("macro_china_cpi", ak.macro_china_cpi, logger_=logger)


def fetch_china_ppi() -> pd.DataFrame | None:
    return safe_retry_df("macro_china_ppi", ak.macro_china_ppi, logger_=logger)


def fetch_china_pmi() -> pd.DataFrame | None:
    return safe_retry_df("macro_china_pmi", ak.macro_china_pmi, logger_=logger)


def fetch_china_consumer_confidence() -> pd.DataFrame | None:
    return safe_retry_df("macro_china_xfzxx", ak.macro_china_xfzxx, logger_=logger)


def fetch_usa_cpi_yoy() -> pd.DataFrame | None:
    return safe_retry_df("macro_usa_cpi_yoy", ak.macro_usa_cpi_yoy, logger_=logger)


def fetch_bond_zh_us_rate() -> pd.DataFrame | None:
    return safe_retry_df("bond_zh_us_rate", ak.bond_zh_us_rate, logger_=logger)


def fetch_boc_forex(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
) -> pd.DataFrame | None:
    return safe_retry_df(
        f"currency_boc_sina:{symbol}",
        lambda: ak.currency_boc_sina(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        ),
        logger_=logger,
    )
