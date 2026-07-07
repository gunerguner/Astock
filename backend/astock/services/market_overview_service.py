"""全球市场概览：Redis 缓存 + 日/周涨跌计算。"""

import logging

from astock.config import (
    ASSET_PRICE_CACHE_TTL,
    MARKET_OVERVIEW_CATEGORIES,
    MARKET_OVERVIEW_FAILURE_TTL,
    MARKET_OVERVIEW_ITEMS,
)
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
    MarketOverviewItem,
    MarketOverviewResponse,
)
from astock.services.price_utils import (
    baseline_prices,
    iso_now,
    latest_trading_date,
    pct_change,
    read_recent_closes_cache,
    sorted_dates,
    write_recent_closes_cache,
)
from astock.sources.market_overview_client import fetch_all_items

logger = logging.getLogger(__name__)


def _write_cache(item_key: str, closes: dict[str, float]) -> None:
    write_recent_closes_cache(
        set_json,
        market_overview_recent_key(item_key),
        closes,
        ttl=ASSET_PRICE_CACHE_TTL,
    )


def _read_cache(item_key: str) -> dict[str, float]:
    return read_recent_closes_cache(get_json, market_overview_recent_key(item_key))


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

    for item in MARKET_OVERVIEW_ITEMS:
        key = item["key"]
        closes = _read_cache(key)
        if closes:
            all_closes[key] = closes
        elif not force_refresh and _has_failure_marker(key):
            continue
        else:
            missing.append(item)

    if not missing:
        latest = get_string(MARKET_OVERVIEW_LATEST_DATE_KEY)
        if latest is None:
            latest = latest_trading_date(all_closes)
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
        existing = _read_cache(key)
        new_closes = backfill.get(key, {})
        merged = {**existing, **new_closes}
        if merged:
            all_closes[key] = merged
            _write_cache(key, merged)
            _clear_failure_marker(key)
        else:
            _write_failure_marker(key)

    latest = latest_trading_date(all_closes)
    if latest:
        set_string(MARKET_OVERVIEW_LATEST_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return all_closes, errors


def _build_item(item: dict[str, str], closes: dict[str, float]) -> MarketOverviewItem:
    current, prev_close, week_ago_close = baseline_prices(closes)
    daily = pct_change(current, prev_close) if current is not None else None
    weekly = pct_change(current, week_ago_close) if current is not None else None
    dates = sorted_dates(closes)
    return MarketOverviewItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        current_price=round(current, 4) if current is not None else None,
        daily_change=round(daily, 2) if daily is not None else None,
        weekly_change=round(weekly, 2) if weekly is not None else None,
        period_start=dates[-2] if len(dates) >= 2 else dates[-1] if dates else None,
        period_end=dates[-1] if dates else None,
        error=None,
    )


def _error_item(item: dict[str, str], message: str) -> MarketOverviewItem:
    return MarketOverviewItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        error=message,
    )


def get_market_overview(*, force_refresh: bool = False) -> MarketOverviewResponse:
    all_closes, cache_errors = _ensure_closes(force_refresh=force_refresh)
    as_of = iso_now()

    item_map = {item["key"]: item for item in MARKET_OVERVIEW_ITEMS}
    categories: list[MarketOverviewCategory] = []

    for cat in MARKET_OVERVIEW_CATEGORIES:
        cat_items: list[MarketOverviewItem] = []
        for raw_item in cat["items"]:
            item_key = f"{cat['key']}:{raw_item['code']}"
            item = item_map.get(item_key)
            if item is None:
                continue
            closes = all_closes.get(item_key, {})
            if closes:
                cat_items.append(_build_item(item, closes))
            else:
                cat_items.append(_error_item(item, "数据获取失败"))

        categories.append(
            MarketOverviewCategory(
                key=cat["key"],
                name=cat["display_name"],
                items=cat_items,
            )
        )

    latest_trading_date_value = get_string(MARKET_OVERVIEW_LATEST_DATE_KEY) or latest_trading_date(
        all_closes
    )

    return MarketOverviewResponse(
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        categories=categories,
        errors=cache_errors[:10] if cache_errors else None,
    )
