"""market_overview 抓取公共工具。"""

import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import timedelta

import pandas as pd

from astock.config import (
    CN_INDEX_LOOKBACK_DAYS,
    EM_UDI_REFERER,
    EM_USER_AGENT,
    FETCH_RETRIES,
    FETCH_RETRY_DELAY,
    MARKET_OVERVIEW_IGNORE_SYSTEM_PROXY,
)
from astock.core.datetime_utils import normalize_date, now_local

logger = logging.getLogger(__name__)
_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "SOCKS_PROXY",
    "SOCKS5_PROXY",
    "socks_proxy",
    "socks5_proxy",
)
_PROXY_ENV_LOCK = threading.Lock()


@contextmanager
def _without_system_proxy():
    """按配置临时屏蔽代理环境变量，避免抓取链路被本机代理干扰。"""
    if not MARKET_OVERVIEW_IGNORE_SYSTEM_PROXY:
        yield
        return

    with _PROXY_ENV_LOCK:
        old_values = {k: os.environ.pop(k, None) for k in _PROXY_ENV_KEYS}
        try:
            yield
        finally:
            for key, value in old_values.items():
                if value is not None:
                    os.environ[key] = value


def _retry_call[T](label: str, fn: Callable[[], T]) -> T:
    last: Exception | None = None
    for attempt in range(FETCH_RETRIES):
        try:
            with _without_system_proxy():
                return fn()
        except Exception as e:
            last = e
            if attempt < FETCH_RETRIES - 1:
                logger.warning("%s 第 %s 次失败，重试: %s", label, attempt + 1, e)
                time.sleep(FETCH_RETRY_DELAY * (attempt + 1))
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


def _merge_close_dicts(*sources: dict[str, float], n: int) -> dict[str, float]:
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return _tail_closes(sorted(merged.items()), n)


def _cn_index_cutoff():
    return now_local() - timedelta(days=CN_INDEX_LOOKBACK_DAYS)
