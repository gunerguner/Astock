"""全球市场概览：Redis 缓存 + 日/周涨跌计算。"""

import logging

from astock.config import (
    ASSET_PRICE_CACHE_TTL,
    MARKET_OVERVIEW_CATEGORIES,
    MARKET_OVERVIEW_FAILURE_TTL,
    MARKET_OVERVIEW_ITEMS,
)
from astock.core.datetime_utils import last_settled_date, market_for_source
from astock.core.redis_client import (
    MARKET_OVERVIEW_LATEST_DATE_KEY,
    delete_key,
    get_json,
    get_string,
    market_overview_failure_key,
    market_overview_recent_key,
    set_json,
    set_string,
)
from astock.schemas.analysis import (
    MarketOverviewCategory,
    MarketOverviewErrorItem,
    MarketOverviewItem,
    MarketOverviewResponse,
)
from astock.services.price_utils import (
    anchor_date_for_closes,
    anchor_date_excluding_today,
    baseline_prices_at_anchor,
    has_sufficient_baseline_points,
    iso_now,
    overview_item_markets,
    pct_change,
    read_recent_closes_cache,
    sorted_dates,
    write_recent_closes_cache,
)
from astock.sources.market_overview import fetch_all_items

logger = logging.getLogger(__name__)


def _write_cache(item_key: str, closes: dict[str, float], *, market: str) -> None:
    write_recent_closes_cache(
        set_json,
        market_overview_recent_key(item_key),
        closes,
        ttl=ASSET_PRICE_CACHE_TTL,
        market=market,
    )


def _read_cache(item_key: str, *, market: str) -> dict[str, float]:
    return read_recent_closes_cache(
        get_json,
        market_overview_recent_key(item_key),
        market=market,
    )


def _has_failure_marker(item_key: str) -> bool:
    return get_string(market_overview_failure_key(item_key)) is not None


def _write_failure_marker(item_key: str) -> None:
    set_string(
        market_overview_failure_key(item_key),
        "1",
        ttl=MARKET_OVERVIEW_FAILURE_TTL,
    )


def _clear_failure_marker(item_key: str) -> None:
    delete_key(market_overview_failure_key(item_key))


def _ensure_closes(
    *, force_refresh: bool = False
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """确保各资产收盘价可用。

    无论 force_refresh 与否，凡是仍有未过期成功缓存（TTL 内，即已是最新交易日数据）的
    资产一律直接复用，不重新拉取——"强制刷新"只应补齐真正缺失/已过期/此前失败的部分，
    而不是无条件重新下载全部资产的完整历史。force_refresh 与默认模式的唯一区别是：
    是否忽略"近期抓取失败"标记，强制重试这些项。
    """
    all_closes: dict[str, dict[str, float]] = {}
    missing: list[dict[str, str]] = []

    item_markets = overview_item_markets(MARKET_OVERVIEW_ITEMS)

    for item in MARKET_OVERVIEW_ITEMS:
        key = item["key"]
        market = item_markets[key]
        closes = _read_cache(key, market=market)
        if closes:
            all_closes[key] = closes
            if has_sufficient_baseline_points(closes, market=market):
                continue
            if not force_refresh and _has_failure_marker(key):
                continue
            missing.append(item)
        elif not force_refresh and _has_failure_marker(key):
            continue
        else:
            missing.append(item)

    if not missing:
        latest = get_string(MARKET_OVERVIEW_LATEST_DATE_KEY)
        if latest is None:
            latest = anchor_date_excluding_today(all_closes, markets=item_markets)
            if latest:
                set_string(
                    MARKET_OVERVIEW_LATEST_DATE_KEY,
                    latest,
                    ttl=ASSET_PRICE_CACHE_TTL,
                )
        return all_closes, []

    backfill, errors = fetch_all_items(missing)
    for item in missing:
        key = item["key"]
        existing = _read_cache(key, market=item_markets[key])
        new_closes = backfill.get(key, {})
        merged = {**existing, **new_closes}
        if merged:
            all_closes[key] = merged
            _write_cache(key, merged, market=item_markets[key])
            if has_sufficient_baseline_points(merged, market=item_markets[key]):
                _clear_failure_marker(key)
            else:
                _write_failure_marker(key)
        else:
            _write_failure_marker(key)

    latest = anchor_date_excluding_today(all_closes, markets=item_markets)
    if latest:
        set_string(MARKET_OVERVIEW_LATEST_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return all_closes, errors


def _build_item(
    item: dict[str, str],
    closes: dict[str, float],
    anchor_date: str,
) -> MarketOverviewItem | MarketOverviewErrorItem:
    current, prev_close, week_ago_close = baseline_prices_at_anchor(closes, anchor_date)
    if current is None:
        return _error_item(item, f"{item['name']}({item['code']}): 当前价格缺失")
    daily = pct_change(current, prev_close)
    weekly = pct_change(current, week_ago_close)
    dates = [d for d in sorted_dates(closes) if d <= anchor_date]
    period_end = dates[-1] if dates else None
    period_start = dates[-2] if len(dates) >= 2 else period_end
    return MarketOverviewItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        current_price=round(current, 4),
        daily_change=round(daily, 2) if daily is not None else None,
        weekly_change=round(weekly, 2) if weekly is not None else None,
        period_start=period_start,
        period_end=period_end,
    )


def _error_item(item: dict[str, str], message: str) -> MarketOverviewErrorItem:
    return MarketOverviewErrorItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        error=message,
    )


def get_market_overview(*, force_refresh: bool = False) -> MarketOverviewResponse:
    all_closes, cache_errors = _ensure_closes(force_refresh=force_refresh)
    as_of = iso_now()
    item_markets = overview_item_markets(MARKET_OVERVIEW_ITEMS)

    item_map = {item["key"]: item for item in MARKET_OVERVIEW_ITEMS}
    categories: list[MarketOverviewCategory] = []

    for cat in MARKET_OVERVIEW_CATEGORIES:
        cat_items: list[MarketOverviewItem | MarketOverviewErrorItem] = []
        for raw_item in cat["items"]:
            item_key = f"{cat['key']}:{raw_item['code']}"
            item = item_map.get(item_key)
            if item is None:
                continue
            closes = all_closes.get(item_key, {})
            if not closes:
                cat_items.append(_error_item(item, "数据获取失败"))
                continue
            anchor_date = anchor_date_for_closes(closes, item_markets[item_key])
            if anchor_date is None:
                cat_items.append(_error_item(item, "无法确定最新交易日"))
                continue
            cat_items.append(_build_item(item, closes, anchor_date))

        categories.append(
            MarketOverviewCategory(
                key=cat["key"],
                name=cat["display_name"],
                items=cat_items,
            )
        )

    latest_trading_date_value = (
        anchor_date_excluding_today(all_closes, markets=item_markets)
        or get_string(MARKET_OVERVIEW_LATEST_DATE_KEY)
        or last_settled_date("cn")
    )
    if not all_closes:
        cache_errors = [
            *(cache_errors or []),
            "无法确定最新交易日，请先刷新市场概览数据",
        ]

    return MarketOverviewResponse(
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        categories=categories,
        errors=cache_errors[:10] if cache_errors else None,
    )
