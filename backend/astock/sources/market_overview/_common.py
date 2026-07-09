"""market_overview 抓取公共工具。"""

from datetime import timedelta

import pandas as pd

from astock.config import (
    CN_INDEX_LOOKBACK_DAYS,
    EM_UDI_REFERER,
    EM_USER_AGENT,
)
from astock.core.datetime_utils import MarketCode, last_settled_date, normalize_date, now_local
from astock.sources.retry import retry_call
from astock.sources.symbols import cn_index_sina_symbol

# 兼容旧 import 名
_retry_call = retry_call
_cn_index_sina_symbol = cn_index_sina_symbol


def _tail_closes(
    date_close_pairs: list[tuple[str, float]],
    n: int,
    *,
    market: MarketCode = "cn",
) -> dict[str, float]:
    if not date_close_pairs:
        return {}
    cap = last_settled_date(market)
    filtered = [(d, c) for d, c in date_close_pairs if d <= cap]
    if not filtered:
        return {}
    sorted_pairs = sorted(filtered, key=lambda x: x[0])
    return dict(sorted_pairs[-n:])


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
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return _tail_closes(sorted(merged.items()), n, market=market)


def _cn_index_cutoff():
    return now_local() - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
