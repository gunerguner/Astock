"""Redis 收盘价缓存：读写 / ensure / 涨跌展示字段构建。"""

from collections.abc import Callable
from typing import Any

from astock.core.datetime_utils import MarketCode, filter_settled_closes
from astock.core.price_utils import (
    anchor_date_excluding_today,
    baseline_prices_at_anchor,
    has_sufficient_baseline_points,
    pct_change,
    sorted_dates,
)
from astock.core.redis_client import get_string, set_string

ReadClosesFn = Callable[[str, MarketCode], dict[str, float]]
WriteClosesFn = Callable[[str, dict[str, float], MarketCode], None]
FetchMissingFn = Callable[
    [list[dict[str, str]]],
    tuple[dict[str, dict[str, float]], list[str]],
]


def read_recent_closes_cache(
    get_json: Callable[[str], Any | None],
    key: str,
    *,
    market: MarketCode = "cn",
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
    return filter_settled_closes(closes, market)


def write_recent_closes_cache(
    set_json: Callable[..., bool],
    key: str,
    closes: dict[str, float],
    *,
    ttl: int,
    market: MarketCode = "cn",
) -> None:
    if not closes:
        return
    settled = filter_settled_closes(closes, market)
    if not settled:
        return
    sorted_items = sorted(settled.items())
    set_json(
        key,
        [{"date": d, "close": price} for d, price in sorted_items],
        ttl=ttl,
    )


def build_change_fields(
    closes: dict[str, float],
    anchor_date: str,
) -> dict[str, Any]:
    """从 closes + 锚点日构建涨跌展示字段。"""
    current, prev_close, week_ago_close = baseline_prices_at_anchor(closes, anchor_date)
    daily = pct_change(current, prev_close) if current is not None else None
    weekly = pct_change(current, week_ago_close) if current is not None else None
    dates = [d for d in sorted_dates(closes) if d <= anchor_date]
    period_end = dates[-1] if dates else None
    period_start = dates[-2] if len(dates) >= 2 else period_end
    return {
        "current_price": round(current, 4) if current is not None else None,
        "daily_change": round(daily, 2) if daily is not None else None,
        "weekly_change": round(weekly, 2) if weekly is not None else None,
        "period_start": period_start,
        "period_end": period_end,
        "prev_close": prev_close,
        "week_ago_close": week_ago_close,
        "current": current,
    }


def ensure_closes(
    items: list[dict[str, str]],
    *,
    key_fn: Callable[[dict[str, str]], str],
    market_fn: Callable[[dict[str, str]], MarketCode],
    read_closes: ReadClosesFn,
    write_closes: WriteClosesFn,
    fetch_missing: FetchMissingFn,
    latest_date_key: str,
    latest_ttl: int,
    force_refresh: bool = False,
    require_baseline: bool = False,
    has_failure: Callable[[str], bool] | None = None,
    write_failure: Callable[[str], None] | None = None,
    clear_failure: Callable[[str], None] | None = None,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """读缓存 → 判缺失 → 回填 → 更新 latest 锚点。

    force_refresh 时仍复用未过期成功缓存；仅对缺失/不足/失败标记项重试。
    """
    all_closes: dict[str, dict[str, float]] = {}
    missing: list[dict[str, str]] = []
    markets: dict[str, MarketCode] = {}

    for item in items:
        key = key_fn(item)
        market = market_fn(item)
        markets[key] = market
        closes = read_closes(key, market)
        if closes:
            all_closes[key] = closes
            if require_baseline and not has_sufficient_baseline_points(closes, market=market):
                if not force_refresh and has_failure and has_failure(key):
                    continue
                missing.append(item)
            continue
        if not force_refresh and has_failure and has_failure(key):
            continue
        missing.append(item)

    if not missing:
        latest = get_string(latest_date_key)
        if latest is None:
            latest = anchor_date_excluding_today(all_closes, markets=markets)
            if latest:
                set_string(latest_date_key, latest, ttl=latest_ttl)
        return all_closes, []

    backfill, errors = fetch_missing(missing)
    for item in missing:
        key = key_fn(item)
        market = markets[key]
        existing = read_closes(key, market)
        new_closes = backfill.get(key, {})
        merged = {**existing, **new_closes}
        if merged:
            all_closes[key] = merged
            write_closes(key, merged, market)
            if require_baseline:
                if has_sufficient_baseline_points(merged, market=market):
                    if clear_failure:
                        clear_failure(key)
                elif write_failure:
                    write_failure(key)
            elif clear_failure:
                clear_failure(key)
        elif write_failure:
            write_failure(key)

    latest = anchor_date_excluding_today(all_closes, markets=markets)
    if latest:
        set_string(latest_date_key, latest, ttl=latest_ttl)
    return all_closes, errors


def redis_closes_io(
    key_builder: Callable[[str], str],
    *,
    ttl: int,
):
    """返回 (read_fn, write_fn) 绑定到同一 Redis key 前缀。"""
    from astock.core.redis_client import get_json, set_json

    def read_fn(key: str, market: MarketCode) -> dict[str, float]:
        return read_recent_closes_cache(get_json, key_builder(key), market=market)

    def write_fn(key: str, closes: dict[str, float], market: MarketCode) -> None:
        write_recent_closes_cache(
            set_json, key_builder(key), closes, ttl=ttl, market=market
        )

    return read_fn, write_fn
