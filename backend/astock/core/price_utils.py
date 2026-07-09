"""价格与日期相关的纯函数（无 Redis / 无外部 IO）。"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from astock.config import WEEKLY_BASELINE_OFFSET
from astock.core.datetime_utils import (
    MarketCode,
    last_settled_date,
    market_for_asset_type,
    market_for_source,
)

__all__ = [
    "BaselinePrices",
    "sorted_dates",
    "pct_change",
    "baseline_prices",
    "baseline_prices_at_anchor",
    "anchor_date_for_closes",
    "anchor_date_excluding_today",
    "closes_cover_settled",
    "has_sufficient_baseline_points",
    "overview_item_markets",
    "global_asset_markets",
]


@dataclass(frozen=True)
class BaselinePrices:
    """锚点日口径下的当前价与昨收、约一周前基准价。"""

    current: float | None
    prev: float | None
    week_ago: float | None


def sorted_dates(closes: dict[str, float]) -> list[str]:
    """将收盘价字典的日期键排序为升序列表。"""
    return sorted(closes.keys())


def pct_change(cur: float, base: float | None) -> float | None:
    """按基准价计算当前价的百分比涨跌幅。"""
    if base and base > 0:
        return (cur - base) / base * 100
    return None


def baseline_prices(closes: dict[str, float]) -> BaselinePrices:
    """返回最近交易日的当前价、昨收基准与约 5 个交易日前基准。"""
    dates = sorted_dates(closes)
    if not dates:
        return BaselinePrices(None, None, None)
    current = closes[dates[-1]]
    prev = closes[dates[-2]] if len(dates) >= 2 else None
    week_ago = closes[dates[-WEEKLY_BASELINE_OFFSET]] if len(dates) >= WEEKLY_BASELINE_OFFSET else None
    return BaselinePrices(current, prev, week_ago)


def baseline_prices_at_anchor(closes: dict[str, float], anchor_date: str) -> BaselinePrices:
    """返回给定锚点交易日内的当前价、昨收基准与约 5 个交易日前基准。"""
    dates = [d for d in sorted_dates(closes) if d <= anchor_date]
    if not dates:
        return BaselinePrices(None, None, None)
    current = closes[dates[-1]]
    prev = closes[dates[-2]] if len(dates) >= 2 else None
    week_ago = (
        closes[dates[-WEEKLY_BASELINE_OFFSET]]
        if len(dates) >= WEEKLY_BASELINE_OFFSET
        else None
    )
    return BaselinePrices(current, prev, week_ago)


def anchor_date_for_closes(
    closes: dict[str, float],
    market: MarketCode = "cn",
) -> str | None:
    """单资产在对应市场结算日上界内的最新交易日。"""
    cap = last_settled_date(market)
    dates = [d for d in closes if d <= cap]
    return max(dates) if dates else None


def closes_cover_settled(
    closes: dict[str, float],
    market: MarketCode = "cn",
) -> bool:
    """缓存是否已覆盖该市场最近可结算日（「最近一个收盘日」口径）。

    无交易日历：若缓存最新日已达结算日，或二者之间仅隔周末，视为已覆盖；
    中间若缺工作日（如停在周二而结算日已是周四）则未覆盖，需回填。
    """
    if not closes:
        return False
    cap = last_settled_date(market)
    latest = max(closes)
    if latest >= cap:
        return True
    cursor = datetime.strptime(latest, "%Y-%m-%d").date() + timedelta(days=1)
    end = datetime.strptime(cap, "%Y-%m-%d").date()
    while cursor <= end:
        if cursor.weekday() < 5:
            return False
        cursor += timedelta(days=1)
    return True


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
    """为市场概览条目建立 key → 结算市场映射。"""
    return {item["key"]: market_for_source(item["source"]) for item in items}


def global_asset_markets(assets: list[dict[str, str]]) -> dict[str, MarketCode]:
    """为全球资产建立 ticker → 结算市场映射。"""
    return {asset["ticker"]: market_for_asset_type(asset["asset_type"]) for asset in assets}
