"""market_overview 数据集专属：近期收盘价裁剪与合并。"""


from datetime import timedelta

import pandas as pd

from astock.config import CN_INDEX_LOOKBACK_DAYS
from astock.core.datetime_utils import MarketCode, last_settled_date, normalize_date, now_local


def tail_closes(
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
    return tail_closes(pairs, n, market=market)


def merge_close_dicts(
    *sources: dict[str, float], n: int, market: MarketCode = "cn"
) -> dict[str, float]:
    """合并多段收盘价字典后取近期 n 个结算日。"""
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return tail_closes(sorted(merged.items()), n, market=market)


def cn_index_cutoff():
    return now_local() - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
