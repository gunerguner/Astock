"""市场概览本地 closes：优先复用 SQLite point 与全球资产 Redis。"""

import logging

from sqlmodel import Session, col, select

from astock.config import MARKET_OVERVIEW_RECENT_DAYS
from astock.core.database import engine
from astock.core.datetime_utils import MarketCode, filter_settled_closes, market_for_source
from astock.core.price_utils import closes_cover_settled, has_sufficient_baseline_points
from astock.models.point import Point
from astock.services.global_asset._cache import read_price_cache

logger = logging.getLogger(__name__)

# 全球资产已覆盖的外盘期货代码（概览 WTI/CL 不在此列）
_GLOBAL_ASSET_METAL_CODES = frozenset({"GC", "SI"})


def _usable(closes: dict[str, float], market: MarketCode) -> dict[str, float]:
    """结算日过滤后，覆盖最近结算日且基准点足够则返回，否则空。"""
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


def _read_point_closes(index_code: str) -> dict[str, float]:
    """从 point 表取近期收盘价（含科创50）。"""
    limit = max(MARKET_OVERVIEW_RECENT_DAYS, 20)
    with Session(engine) as db:
        rows = db.exec(
            select(Point.date, Point.close)
            .where(Point.index_code == index_code)
            .order_by(col(Point.date).desc())
            .limit(limit)
        ).all()
    if not rows:
        return {}
    return {str(date): float(close) for date, close in reversed(rows)}


def _try_cn_index(item: dict[str, str]) -> dict[str, float]:
    market = market_for_source(item["source"])
    closes = _read_point_closes(item["code"])
    usable = _usable(closes, market)
    if usable:
        logger.info("概览本地命中 point: %s (%s)", item["key"], item["code"])
    return usable


def _try_foreign_futures(item: dict[str, str]) -> dict[str, float]:
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
    items: list[dict[str, str]],
) -> tuple[dict[str, dict[str, float]], list[dict[str, str]]]:
    """用本地数据填概览项；返回 (已填充 closes, 仍需外网的 items)。"""
    filled: dict[str, dict[str, float]] = {}
    still_missing: list[dict[str, str]] = []

    for item in items:
        source = item["source"]
        closes: dict[str, float] = {}
        if source == "cn_index":
            closes = _try_cn_index(item)
        elif source == "foreign_futures":
            closes = _try_foreign_futures(item)

        if closes:
            filled[item["key"]] = closes
        else:
            still_missing.append(item)

    return filled, still_missing
