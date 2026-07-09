"""market_overview 抓取公共工具。"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pandas as pd

from astock.config import (
    CN_INDEX_LOOKBACK_DAYS,
    EM_UDI_REFERER,
    EM_USER_AGENT,
)
from astock.core.datetime_utils import MarketCode, last_settled_date, normalize_date, now_local


def _tail_closes(
    date_close_pairs: list[tuple[str, float]],
    n: int,
    *,
    market: MarketCode = "cn",
) -> dict[str, float]:
    """在结算日上界内取最近 n 个交易日的收盘价序列。"""
    if not date_close_pairs:
        return {}
    cap = last_settled_date(market)
    filtered = [(d, c) for d, c in date_close_pairs if d <= cap]
    if not filtered:
        return {}
    sorted_pairs = sorted(filtered, key=lambda x: x[0])
    return dict(sorted_pairs[-n:])


def df_to_tail_closes(
    df: pd.DataFrame,
    n: int,
    *,
    date_col: str,
    value_col: str,
    market: MarketCode = "cn",
    scale: float = 1.0,
) -> dict[str, float]:
    """从 DataFrame 提取日期收盘价并转为近期 n 日结算序列。"""
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = normalize_date(row.get(date_col))
        val = pd.to_numeric(row.get(value_col), errors="coerce")
        if d and pd.notna(val):
            pairs.append((d, float(val) * scale))
    return _tail_closes(pairs, n, market=market)


def safe_retry_df(
    label: str,
    fn: Callable[[], Any],
    *,
    logger,
) -> pd.DataFrame | None:
    """带重试地执行 DataFrame 抓取，失败或空表时返回 None。"""
    from astock.sources.retry import retry_call

    try:
        df = retry_call(label, fn)
    except Exception as e:
        logger.warning("%s 失败: %s", label, e)
        return None
    if df is None or getattr(df, "empty", True):
        return None
    return df


def _em_udi_headers() -> dict[str, str]:
    return {
        "User-Agent": EM_USER_AGENT,
        "Referer": EM_UDI_REFERER,
        "Connection": "close",
    }


def _parse_em_kline_lines(klines: list[str]) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        d = normalize_date(parts[0])
        close = pd.to_numeric(parts[2], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return pairs


def _merge_close_dicts(*sources: dict[str, float], n: int, market: MarketCode = "cn") -> dict[str, float]:
    """合并多段收盘价字典后取近期 n 个结算日。"""
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return _tail_closes(sorted(merged.items()), n, market=market)


def _cn_index_cutoff():
    return now_local() - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
