"""akshare 宏观/债券/汇率原始查询。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import akshare as ak
import pandas as pd

from astock.providers._shared.retry import safe_retry_df

logger = logging.getLogger(__name__)


def _macro_df(label: str, fn: Callable[[], Any]) -> pd.DataFrame | None:
    return safe_retry_df(label, fn, logger_=logger)


def fetch_china_cpi() -> pd.DataFrame | None:
    return _macro_df("macro_china_cpi", ak.macro_china_cpi)


def fetch_china_ppi() -> pd.DataFrame | None:
    return _macro_df("macro_china_ppi", ak.macro_china_ppi)


def fetch_china_pmi() -> pd.DataFrame | None:
    return _macro_df("macro_china_pmi", ak.macro_china_pmi)


def fetch_china_consumer_confidence() -> pd.DataFrame | None:
    return _macro_df("macro_china_xfzxx", ak.macro_china_xfzxx)


def fetch_usa_cpi_yoy() -> pd.DataFrame | None:
    return _macro_df("macro_usa_cpi_yoy", ak.macro_usa_cpi_yoy)


def fetch_bond_zh_us_rate() -> pd.DataFrame | None:
    return _macro_df("bond_zh_us_rate", ak.bond_zh_us_rate)


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
