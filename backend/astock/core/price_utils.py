"""价格与日期相关的纯函数（无 Redis / 无外部 IO）。"""

from astock.config import WEEKLY_BASELINE_OFFSET
from astock.core.datetime_utils import (
    MarketCode,
    iso_now,
    last_settled_date,
    market_for_asset_type,
    market_for_source,
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


def anchor_date_for_closes(
    closes: dict[str, float],
    market: MarketCode = "cn",
) -> str | None:
    """单资产在对应市场结算日上界内的最新交易日。"""
    cap = last_settled_date(market)
    dates = [d for d in closes if d <= cap]
    return max(dates) if dates else None


def anchor_date_excluding_today(
    all_closes: dict[str, dict[str, float]],
    *,
    markets: dict[str, MarketCode] | None = None,
    default_market: MarketCode = "cn",
) -> str | None:
    """多资产取各市场结算日后的全局最新锚点（用于展示「数据截至」）。"""
    anchors: list[str] = []
    for key, closes in all_closes.items():
        market = (markets or {}).get(key, default_market)
        anchor = anchor_date_for_closes(closes, market)
        if anchor:
            anchors.append(anchor)
    return max(anchors) if anchors else None


def has_sufficient_baseline_points(
    closes: dict[str, float],
    anchor_date: str | None = None,
    *,
    market: MarketCode = "cn",
) -> bool:
    """判断在锚点日口径下是否足以计算日/周涨跌（至少 WEEKLY_BASELINE_OFFSET 个交易日点）。"""
    if not closes:
        return False
    anchor = anchor_date
    if anchor is None:
        anchor = anchor_date_for_closes(closes, market)
    if anchor is None:
        return False
    dates = [d for d in sorted_dates(closes) if d <= anchor]
    return len(dates) >= WEEKLY_BASELINE_OFFSET


def overview_item_markets(items: list[dict[str, str]]) -> dict[str, MarketCode]:
    return {item["key"]: market_for_source(item["source"]) for item in items}


def global_asset_markets(assets: list[dict[str, str]]) -> dict[str, MarketCode]:
    return {asset["ticker"]: market_for_asset_type(asset["asset_type"]) for asset in assets}
