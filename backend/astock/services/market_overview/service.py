"""全球市场概览：Redis 缓存 + 日/周涨跌计算。"""

import logging

from astock.config import (
    ASSET_PRICE_CACHE_TTL,
    MARKET_OVERVIEW_CATEGORIES,
    MARKET_OVERVIEW_FAILURE_TTL,
    MARKET_OVERVIEW_ITEMS,
)
from astock.core.datetime_utils import iso_now, last_settled_date
from astock.core.price_utils import (
    anchor_date_excluding_today,
    anchor_date_for_closes,
    overview_item_markets,
)
from astock.core.redis_client import (
    MARKET_OVERVIEW_LATEST_DATE_KEY,
    delete_key,
    get_string,
    market_overview_failure_key,
    market_overview_recent_key,
    set_string,
)
from astock.schemas.analysis import (
    MarketOverviewCategory,
    MarketOverviewErrorItem,
    MarketOverviewItem,
    MarketOverviewResponse,
)
from astock.services.closes_cache import (
    ClosesCacheDeps,
    ClosesEnsureOptions,
    ClosesFetchResult,
    build_change_fields,
    ensure_closes,
    redis_closes_io,
)
from astock.services.market_overview.local_closes import fill_closes_from_local
from astock.sources.market_overview import fetch_all_items

logger = logging.getLogger(__name__)

_read_closes, _write_closes = redis_closes_io(
    market_overview_recent_key, ttl=ASSET_PRICE_CACHE_TTL
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


def _fetch_missing(missing: list[dict[str, str]]) -> ClosesFetchResult:
    """先本地（point / 全球资产 Redis），不足项再外网抓取。"""
    local_closes, still_missing = fill_closes_from_local(missing)
    if not still_missing:
        return ClosesFetchResult(local_closes, [])
    remote = fetch_all_items(still_missing)
    return ClosesFetchResult({**local_closes, **remote.closes}, list(remote.errors))


def _ensure_closes(*, force_refresh: bool = False) -> ClosesFetchResult:
    """确保概览项收盘价缓存齐全，不足基准点时触发回填并管理失败标记。"""
    item_markets = overview_item_markets(MARKET_OVERVIEW_ITEMS)
    deps = ClosesCacheDeps(
        key_fn=lambda item: item["key"],
        market_fn=lambda item: item_markets[item["key"]],
        read_closes=_read_closes,
        write_closes=_write_closes,
        fetch_missing=_fetch_missing,
        latest_date_key=MARKET_OVERVIEW_LATEST_DATE_KEY,
        latest_ttl=ASSET_PRICE_CACHE_TTL,
    )
    options = ClosesEnsureOptions(
        force_refresh=force_refresh,
        require_baseline=True,
        has_failure=_has_failure_marker,
        write_failure=_write_failure_marker,
        clear_failure=_clear_failure_marker,
    )
    return ensure_closes(MARKET_OVERVIEW_ITEMS, deps, options)


def _build_item(
    item: dict[str, str],
    closes: dict[str, float],
    anchor_date: str,
) -> MarketOverviewItem | MarketOverviewErrorItem:
    """将单条概览配置与收盘价序列组装为成功或缺价错误项。"""
    fields = build_change_fields(closes, anchor_date)
    if fields.current is None:
        return _error_item(item, f"{item['name']}({item['code']}): 当前价格缺失")
    return MarketOverviewItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        current_price=fields.current_price,
        daily_change=fields.daily_change,
        weekly_change=fields.weekly_change,
        period_start=fields.period_start,
        period_end=fields.period_end,
    )


def _error_item(item: dict[str, str], message: str) -> MarketOverviewErrorItem:
    return MarketOverviewErrorItem(
        key=item["key"],
        name=item["name"],
        code=item["code"],
        error=message,
    )


def warmup_market_overview() -> ClosesFetchResult:
    """管理员导入后轻量预热 Redis（仅补落后项，不 force 全量打源）。"""
    result = _ensure_closes(force_refresh=False)
    logger.info(
        "市场概览预热完成: items=%d errors=%d",
        len(result.closes),
        len(result.errors),
    )
    return result


def get_market_overview(*, force_refresh: bool = False) -> MarketOverviewResponse:
    """按分类返回全球市场概览项的现价、日/周涨跌与数据截至日。"""
    fetched = _ensure_closes(force_refresh=force_refresh)
    all_closes = fetched.closes
    cache_errors = list(fetched.errors)
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
            *cache_errors,
            "无法确定最新交易日，请先刷新市场概览数据",
        ]

    return MarketOverviewResponse(
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        categories=categories,
        errors=cache_errors[:10] if cache_errors else None,
    )
