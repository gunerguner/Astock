"""价格工具：纯函数从 core 再导出；Redis closes 读写留在 services。"""

from collections.abc import Callable
from typing import Any

from astock.core.datetime_utils import MarketCode, filter_settled_closes
from astock.core.price_utils import (  # noqa: F401
    anchor_date_excluding_today,
    anchor_date_for_closes,
    baseline_prices,
    baseline_prices_at_anchor,
    global_asset_markets,
    has_sufficient_baseline_points,
    iso_now,
    overview_item_markets,
    pct_change,
    sorted_dates,
)

__all__ = [
    "iso_now",
    "sorted_dates",
    "pct_change",
    "baseline_prices",
    "baseline_prices_at_anchor",
    "anchor_date_for_closes",
    "anchor_date_excluding_today",
    "has_sufficient_baseline_points",
    "overview_item_markets",
    "global_asset_markets",
    "read_recent_closes_cache",
    "write_recent_closes_cache",
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
