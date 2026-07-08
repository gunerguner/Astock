"""价格与日期相关的共享工具函数。"""

from collections.abc import Callable
from typing import Any

from astock.config import WEEKLY_BASELINE_OFFSET
from astock.core.datetime_utils import iso_now, today_local

__all__ = [
    "iso_now",
    "sorted_dates",
    "pct_change",
    "baseline_prices",
    "baseline_prices_at_anchor",
    "anchor_date_excluding_today",
    "latest_trading_date",
    "read_recent_closes_cache",
    "write_recent_closes_cache",
]


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
    week_ago = closes[dates[-WEEKLY_BASELINE_OFFSET]] if len(dates) >= WEEKLY_BASELINE_OFFSET else None
    return current, prev, week_ago


def baseline_prices_at_anchor(
    closes: dict[str, float],
    anchor_date: str,
) -> tuple[float | None, float | None, float | None]:
    """返回给定锚点交易日的 (当前价, 昨收基准, 约5个交易日前基准)。"""
    dates = [d for d in sorted_dates(closes) if d <= anchor_date]
    if not dates:
        return None, None, None
    current = closes[dates[-1]]
    prev = closes[dates[-2]] if len(dates) >= 2 else None
    week_ago = (
        closes[dates[-WEEKLY_BASELINE_OFFSET]]
        if len(dates) >= WEEKLY_BASELINE_OFFSET
        else None
    )
    return current, prev, week_ago


def anchor_date_excluding_today(all_closes: dict[str, dict[str, float]]) -> str | None:
    """返回小于 today 的最后交易日；若不存在则回退到全量最大日期。"""
    today = today_local()
    dates: set[str] = set()
    for closes in all_closes.values():
        dates.update(closes.keys())
    if not dates:
        return None
    before_today = [d for d in dates if d < today]
    if before_today:
        return max(before_today)
    return max(dates)


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
