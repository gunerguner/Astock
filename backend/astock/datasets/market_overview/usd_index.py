"""美元指数：日线历史为主，现货仅补最新结算日。"""


import logging
import time
from datetime import datetime, timedelta

import pandas as pd

from astock.config import (
    EM_HIST_HOSTS,
    MARKET_OVERVIEW_RECENT_DAYS,
    WEEKLY_BASELINE_OFFSET,
)
from astock.core.datetime_utils import last_settled_date
from astock.core.price_utils import has_sufficient_baseline_points
from astock.datasets.market_overview.common import merge_close_dicts, tail_closes, df_to_tail_closes
from astock.providers.akshare.market import fetch_usd_index_hist_em
from astock.providers import eastmoney, sina

logger = logging.getLogger(__name__)


def _previous_weekday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _spot_pairs_to_closes(
    quote_date: str,
    current: float,
    prev: float | None,
) -> dict[str, float]:
    pairs: list[tuple[str, float]] = [(quote_date, current)]
    if prev is not None and not pd.isna(prev):
        pairs.insert(0, (_previous_weekday(quote_date), float(prev)))
    return tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS, market="us")


def _fetch_usd_index_spot() -> dict[str, float]:
    for fetcher, label in (
        (sina.fetch_diniw_spot, "sina"),
        (eastmoney.fetch_udi_spot, "em"),
    ):
        try:
            quote = fetcher()
            if quote:
                return _spot_pairs_to_closes(
                    quote["quote_date"], quote["current"], quote.get("prev")
                )
        except Exception as e:
            logger.warning("美元指数现货失败(%s): %s", label, e)
    return {}


def _fetch_usd_index_history_sina(n: int) -> dict[str, float]:
    pairs = sina.fetch_diniw_day_k()
    closes = tail_closes(pairs, n, market="us")
    if closes:
        logger.info("美元指数历史来自新浪 DINIW: %s 点", len(closes))
    return closes


def _fetch_usd_index_history_akshare(n: int) -> dict[str, float]:
    for attempt in range(2):
        df = fetch_usd_index_hist_em()
        if df is None:
            if attempt < 1:
                time.sleep(1.0)
            continue
        closes = df_to_tail_closes(df, n, date_col="日期", value_col="收盘", market="us")
        if closes:
            logger.info("美元指数历史来自 akshare: %s 点", len(closes))
            return closes
        if attempt < 1:
            time.sleep(1.0)
    return {}


def _fetch_usd_index_history_em(host: str, n: int) -> dict[str, float]:
    pairs = eastmoney.fetch_udi_history(host, n)
    return tail_closes(pairs, n, market="us")


def _fetch_usd_index_history(n: int) -> dict[str, float]:
    for fetcher, label in (
        (_fetch_usd_index_history_sina, "sina"),
        (_fetch_usd_index_history_akshare, "akshare"),
    ):
        try:
            closes = fetcher(n)
            if closes:
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", label, e)

    for host in EM_HIST_HOSTS:
        try:
            closes = _fetch_usd_index_history_em(host, n)
            if closes:
                logger.info("美元指数历史来自东财 %s: %s 点", host, len(closes))
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", host, e)
    return {}


def _needs_spot_patch(history: dict[str, float]) -> bool:
    if not history:
        return True
    if not has_sufficient_baseline_points(history, market="us"):
        return True
    return max(history) < last_settled_date("us")


def fetch_usd_index(n: int) -> dict[str, float]:
    """日线历史为主；现货仅在历史缺最新结算日或点数不足时补丁合并。"""
    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)
    history = _fetch_usd_index_history(history_n)

    spot: dict[str, float] = {}
    if _needs_spot_patch(history):
        spot = _fetch_usd_index_spot()

    if not history and not spot:
        return {}

    if not spot:
        return history

    merged = merge_close_dicts(history, spot, n=n, market="us")
    if has_sufficient_baseline_points(merged, market="us"):
        return merged

    longer = _fetch_usd_index_history(history_n + 10)
    if longer:
        merged = merge_close_dicts(longer, spot, n=n, market="us")
    return merged
