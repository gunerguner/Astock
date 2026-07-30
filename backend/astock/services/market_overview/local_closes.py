"""市场概览本地 closes：优先复用 SQLite point 与全球资产 Redis。"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlmodel import Session, col, select

from astock.config import MARKET_OVERVIEW_RECENT_DAYS, MarketOverviewItemConfig
from astock.core.database import engine
from astock.core.datetime_utils import MarketCode, filter_settled_closes, market_for_source
from astock.core.price_utils import closes_cover_settled, has_sufficient_baseline_points
from astock.models.point import Point
from astock.services.cache.asset_prices import read_price_cache

logger = logging.getLogger(__name__)

# 全球资产已覆盖的外盘期货代码（概览 WTI/CL 不在此列）
_GLOBAL_ASSET_METAL_CODES = frozenset({"GC", "SI"})


def _usable(closes: dict[str, float], market: MarketCode) -> dict[str, float]:
    """结算日过滤后，覆盖最近结算日且基准点足够则返回，否则空。

    先校验全序列足以定锚点，再截近期尾部并校验周涨跌基准点。
    """
    settled = filter_settled_closes(closes, market)
    if not settled:
        return {}
    if not closes_cover_settled(settled, market):
        return {}
    if not has_sufficient_baseline_points(settled, market=market):
        return {}
    dates = sorted(settled)
    tail = {d: settled[d] for d in dates[-MARKET_OVERVIEW_RECENT_DAYS:]}
    if not has_sufficient_baseline_points(tail, market=market):
        return {}
    return tail


def _read_point_closes_batch(
    index_codes: list[str],
) -> dict[str, dict[str, float]]:
    """一次查询多个指数的近期收盘价。"""
    if not index_codes:
        return {}
    limit = max(MARKET_OVERVIEW_RECENT_DAYS, 20)
    # 每个 code 取最近 limit 条：先按 code/date 倒序拉出后在内存截断
    with Session(engine) as db:
        rows = db.exec(
            select(Point.index_code, Point.date, Point.close)
            .where(col(Point.index_code).in_(index_codes))
            .order_by(col(Point.index_code), col(Point.date).desc())
        ).all()

    by_code: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for index_code, date, close in rows:
        bucket = by_code[str(index_code)]
        if len(bucket) >= limit:
            continue
        bucket.append((str(date), float(close)))

    return {
        code: {d: v for d, v in reversed(pairs)}
        for code, pairs in by_code.items()
    }


def _try_foreign_futures(item: MarketOverviewItemConfig) -> dict[str, float]:
    code = item["code"]
    if code not in _GLOBAL_ASSET_METAL_CODES:
        return {}
    market = market_for_source(item["source"])
    closes = read_price_cache(code, market=market)
    usable = _usable(closes, market)
    if usable:
        logger.info("概览本地命中 global_asset: %s (%s)", item["key"], code)
    return usable


def fill_closes_from_local(
    items: list[MarketOverviewItemConfig],
) -> tuple[dict[str, dict[str, float]], list[MarketOverviewItemConfig]]:
    """用本地数据填概览项；返回 (已填充 closes, 仍需外网的 items)。"""
    filled: dict[str, dict[str, float]] = {}
    still_missing: list[MarketOverviewItemConfig] = []

    cn_items = [item for item in items if item["source"] == "cn_index"]
    other_items = [item for item in items if item["source"] != "cn_index"]

    cn_closes = _read_point_closes_batch([item["code"] for item in cn_items])
    for item in cn_items:
        market = market_for_source(item["source"])
        usable = _usable(cn_closes.get(item["code"], {}), market)
        if usable:
            filled[item["key"]] = usable
            logger.info("概览本地命中 point: %s (%s)", item["key"], item["code"])
        else:
            still_missing.append(item)

    for item in other_items:
        closes: dict[str, float] = {}
        if item["source"] == "foreign_futures":
            closes = _try_foreign_futures(item)
        if closes:
            filled[item["key"]] = closes
        else:
            still_missing.append(item)

    return filled, still_missing
