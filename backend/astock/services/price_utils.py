"""价格与日期相关的共享工具函数。"""

from collections.abc import Callable
from typing import Any

from astock.core.datetime_utils import iso_now

__all__ = ["iso_now", "sorted_dates", "pct_change", "baseline_prices", "latest_trading_date", "read_recent_closes_cache", "write_recent_closes_cache"]


def sorted_dates(closes: dict[str, float]) -> list[str]:
    return sorted(closes.keys())


def pct_change(cur: float, base: float | None) -> float | None:
    if base and base > 0:
        return (cur - base) / base * 100
    return None


def baseline_prices(
    closes: dict[str, float],
) -> tuple[float | None, float | None, float | None]:
    """返回 (当前价, 昨收基准, 约5个交易日前基准)。"""
    dates = sorted_dates(closes)
    if not dates:
        return None, None, None
    current = closes[dates[-1]]
    prev = closes[dates[-2]] if len(dates) >= 2 else None
    week_ago = closes[dates[-6]] if len(dates) >= 6 else None
    return current, prev, week_ago


def latest_trading_date(all_closes: dict[str, dict[str, float]]) -> str | None:
    dates: set[str] = set()
    for closes in all_closes.values():
        dates.update(closes.keys())
    return max(dates) if dates else None


def read_recent_closes_cache(
    get_json: Callable[[str], Any | None],
    key: str,
) -> dict[str, float]:
    cached = get_json(key)
    if not isinstance(cached, list):
        return {}
    closes: dict[str, float] = {}
    for item in cached:
        if not isinstance(item, dict):
            continue
        d = item.get("date")
        close = item.get("close")
        if d and close is not None:
            closes[str(d)] = float(close)
    return closes


def write_recent_closes_cache(
    set_json: Callable[..., bool],
    key: str,
    closes: dict[str, float],
    *,
    ttl: int,
) -> None:
    if not closes:
        return
    sorted_items = sorted(closes.items())
    set_json(
        key,
        [{"date": d, "close": price} for d, price in sorted_items],
        ttl=ttl,
    )
