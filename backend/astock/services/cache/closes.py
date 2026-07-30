"""Redis 收盘价缓存：读写 / ensure / 涨跌展示字段构建。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from astock.core.datetime_utils import MarketCode, filter_settled_closes
from astock.core.price_utils import (
    BaselinePrices,
    anchor_date_excluding_today,
    baseline_prices_at_anchor,
    closes_cover_settled,
    has_sufficient_baseline_points,
    pct_change,
    sorted_dates,
)
from astock.core.redis_client import get_string, set_string

ReadClosesFn = Callable[[str, MarketCode], dict[str, float]]
WriteClosesFn = Callable[[str, dict[str, float], MarketCode], None]
FetchMissingFn = Callable[[list[dict[str, str]]], "ClosesFetchResult"]


@dataclass(frozen=True)
class ClosesFetchResult:
    """多实体收盘价抓取/回填结果：key → {date → price} 与错误列表。"""

    closes: dict[str, dict[str, float]]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClosesCacheDeps:
    """ensure_closes 所需的 Redis 读写与回填依赖。"""

    key_fn: Callable[[dict[str, str]], str]
    market_fn: Callable[[dict[str, str]], MarketCode]
    read_closes: ReadClosesFn
    write_closes: WriteClosesFn
    fetch_missing: FetchMissingFn
    latest_date_key: str
    latest_ttl: int


@dataclass(frozen=True)
class ClosesEnsureOptions:
    """ensure_closes 行为开关与失败标记钩子。"""

    force_refresh: bool = False
    require_baseline: bool = False
    has_failure: Callable[[str], bool] | None = None
    write_failure: Callable[[str], None] | None = None
    clear_failure: Callable[[str], None] | None = None


@dataclass(frozen=True)
class ChangeFields:
    """单资产在锚点日的现价、日/周涨跌与展示区间。"""

    current_price: float | None
    daily_change: float | None
    weekly_change: float | None
    period_start: str | None
    period_end: str | None
    prev_close: float | None
    week_ago_close: float | None
    current: float | None


def read_recent_closes_cache(
    get_json: Callable[[str], Any | None],
    key: str,
    *,
    market: MarketCode = "cn",
) -> dict[str, float]:
    """从 Redis JSON 列表读取近期收盘价并按市场结算日截断。"""
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
    """将已结算收盘价序列写入 Redis 并设置 TTL。"""
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


def build_change_fields(closes: dict[str, float], anchor_date: str) -> ChangeFields:
    """从 closes + 锚点日构建涨跌展示字段。"""
    baselines: BaselinePrices = baseline_prices_at_anchor(closes, anchor_date)
    current = baselines.current
    prev_close = baselines.prev
    week_ago_close = baselines.week_ago
    daily = pct_change(current, prev_close) if current is not None else None
    weekly = pct_change(current, week_ago_close) if current is not None else None
    dates = [d for d in sorted_dates(closes) if d <= anchor_date]
    period_end = dates[-1] if dates else None
    period_start = dates[-2] if len(dates) >= 2 else period_end
    return ChangeFields(
        current_price=round(current, 4) if current is not None else None,
        daily_change=round(daily, 2) if daily is not None else None,
        weekly_change=round(weekly, 2) if weekly is not None else None,
        period_start=period_start,
        period_end=period_end,
        prev_close=prev_close,
        week_ago_close=week_ago_close,
        current=current,
    )


def _should_refetch(
    closes: dict[str, float],
    market: MarketCode,
    *,
    force_refresh: bool,
    require_baseline: bool,
    key: str,
    has_failure: Callable[[str], bool] | None,
) -> bool:
    """是否需要回填：强制刷新 / 无缓存 / 未覆盖最近结算日 / 涨跌基准点不足。"""
    if force_refresh:
        return True
    if not closes:
        return not (has_failure and has_failure(key))
    if not closes_cover_settled(closes, market):
        # 源侧节假日可能仍无结算日 K 线：冷却期内复用旧缓存，避免每次打开都打源
        return not (has_failure and has_failure(key))
    if require_baseline and not has_sufficient_baseline_points(closes, market=market):
        return not (has_failure and has_failure(key))
    return False


def ensure_closes(
    items: list[dict[str, str]],
    deps: ClosesCacheDeps,
    options: ClosesEnsureOptions | None = None,
) -> ClosesFetchResult:
    """读缓存 → 判缺失 → 回填 → 更新 latest 锚点。

    deps 提供 Redis 读写与 fetch_missing；options 控制 force_refresh 与失败标记。
    缓存须覆盖该市场最近可结算日；force_refresh 时对全部项重拉。
    """
    opts = options or ClosesEnsureOptions()
    force_refresh = opts.force_refresh
    require_baseline = opts.require_baseline
    has_failure = opts.has_failure
    write_failure = opts.write_failure
    clear_failure = opts.clear_failure

    all_closes: dict[str, dict[str, float]] = {}
    missing: list[dict[str, str]] = []
    markets: dict[str, MarketCode] = {}

    for item in items:
        key = deps.key_fn(item)
        market = deps.market_fn(item)
        markets[key] = market
        closes = deps.read_closes(key, market)
        if closes:
            all_closes[key] = closes
        if _should_refetch(
            closes,
            market,
            force_refresh=force_refresh,
            require_baseline=require_baseline,
            key=key,
            has_failure=has_failure,
        ):
            missing.append(item)

    if not missing:
        latest = get_string(deps.latest_date_key)
        if latest is None:
            latest = anchor_date_excluding_today(all_closes, markets=markets)
            if latest:
                set_string(deps.latest_date_key, latest, ttl=deps.latest_ttl)
        return ClosesFetchResult(all_closes)

    fetched = deps.fetch_missing(missing)
    for item in missing:
        key = deps.key_fn(item)
        market = markets[key]
        existing = deps.read_closes(key, market)
        new_closes = fetched.closes.get(key, {})
        merged = {**existing, **new_closes}
        if merged:
            all_closes[key] = merged
            deps.write_closes(key, merged, market)
            covered = closes_cover_settled(merged, market)
            baseline_ok = (not require_baseline) or has_sufficient_baseline_points(
                merged, market=market
            )
            if covered and baseline_ok:
                if clear_failure:
                    clear_failure(key)
            elif write_failure:
                # 抓到了但仍落后于结算日（节假日空窗）或基准点不足：短冷却，避免打爆源
                write_failure(key)
        elif write_failure:
            write_failure(key)

    latest = anchor_date_excluding_today(all_closes, markets=markets)
    if latest:
        set_string(deps.latest_date_key, latest, ttl=deps.latest_ttl)
    return ClosesFetchResult(all_closes, fetched.errors)


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
