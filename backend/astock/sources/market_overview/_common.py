"""market_overview 抓取公共工具。"""

import logging
import time
from collections.abc import Callable
from datetime import timedelta

import pandas as pd

from astock.core.datetime_utils import normalize_date, now_local

logger = logging.getLogger(__name__)

_FETCH_RETRIES = 4
_FETCH_RETRY_DELAY = 2.0

_CN_INDEX_LOOKBACK_DAYS = 180

_EM_HIST_HOST = "https://push2his.eastmoney.com"
_EM_DELAY_HOST = "https://push2delay.eastmoney.com"
_EM_UDI_REFERER = "https://quote.eastmoney.com/gb/zsUDI.html"


def _retry_call[T](label: str, fn: Callable[[], T]) -> T:
    last: Exception | None = None
    for attempt in range(_FETCH_RETRIES):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < _FETCH_RETRIES - 1:
                logger.warning("%s 第 %s 次失败，重试: %s", label, attempt + 1, e)
                time.sleep(_FETCH_RETRY_DELAY * (attempt + 1))
    assert last is not None
    raise last


def _tail_closes(date_close_pairs: list[tuple[str, float]], n: int) -> dict[str, float]:
    if not date_close_pairs:
        return {}
    sorted_pairs = sorted(date_close_pairs, key=lambda x: x[0])
    return dict(sorted_pairs[-n:])


def _cn_index_sina_symbol(code: str) -> str:
    code = code.strip()
    prefix = "sz" if code.startswith("399") else "sh"
    return f"{prefix}{code}"


def _em_udi_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": _EM_UDI_REFERER,
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


def _merge_close_dicts(*sources: dict[str, float], n: int) -> dict[str, float]:
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return _tail_closes(sorted(merged.items()), n)


def _cn_index_cutoff():
    return now_local() - timedelta(days=_CN_INDEX_LOOKBACK_DAYS)
