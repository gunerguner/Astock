"""全球资产价格缓存读写。"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from astock.config import ASSET_PRICE_CACHE_TTL, PRICE_LEVEL_CONCLUSIONS, PRICE_LEVEL_DEFAULT
from astock.core.datetime_utils import MarketCode, filter_settled_closes, market_for_asset_type
from astock.core.price_utils import anchor_date_excluding_today, global_asset_markets
from astock.core.redis_client import (
    LATEST_TRADING_DATE_KEY,
    get_json,
    get_string,
    price_key,
    recent_closes_key,
    set_json,
    set_string,
)
from astock.schemas.analysis import PriceLevelPendingItem
from astock.services.closes_cache import ClosesFetchResult, read_recent_closes_cache, write_recent_closes_cache
from astock.sources.akshare import fetch_all_assets
from astock.sources.fetch_result import SourceFetchResult


@dataclass(frozen=True)
class AssetFetchRecord:
    """单资产 AkShare 抓取解析结果。"""

    asset: dict[str, str]
    record: dict[str, Any]
    market: MarketCode
    closes: dict[str, float]


def conclusion(percentage_diff: float) -> str:
    """按距历史最高点百分比映射展示结论文案。"""
    abs_diff = abs(percentage_diff)
    for threshold, label in PRICE_LEVEL_CONCLUSIONS:
        if abs_diff < threshold:
            return label
    return PRICE_LEVEL_DEFAULT


def write_price_cache(ticker: str, closes: dict[str, float], *, market: str) -> None:
    """将已结算收盘价写入按日 Redis 键与近期序列缓存。"""
    settled = filter_settled_closes(closes, market)
    if not settled:
        return
    sorted_items = sorted(settled.items())
    for d, price in sorted_items:
        set_string(price_key(ticker, d), str(price), ttl=ASSET_PRICE_CACHE_TTL)
    write_recent_closes_cache(
        set_json,
        recent_closes_key(ticker),
        settled,
        ttl=ASSET_PRICE_CACHE_TTL,
    )


def read_price_cache(ticker: str, *, market: str) -> dict[str, float]:
    """读取单资产近期收盘价缓存，缺失时回退最新单日价。"""
    closes = read_recent_closes_cache(get_json, recent_closes_key(ticker), market=market)
    if closes:
        return closes

    latest = get_string(LATEST_TRADING_DATE_KEY)
    if latest:
        raw = get_string(price_key(ticker, latest))
        if raw is not None:
            return {latest: float(raw)}
    return {}


def parse_asset_fetch_results(
    assets: list[dict[str, str]],
    fetch_results: Mapping[str, SourceFetchResult],
    *,
    skip_pending: bool = False,
) -> tuple[list[AssetFetchRecord], list[str]]:
    """解析 fetch_all_assets 结果，返回成功记录与错误列表。"""
    parsed: list[AssetFetchRecord] = []
    errors: list[str] = []
    for asset in assets:
        ticker = asset["ticker"]
        if skip_pending and asset.get("data_pending"):
            continue
        result = fetch_results.get(ticker)
        if result is None or not result.ok or not result.records:
            if result:
                errors.extend(result.errors)
            else:
                errors.append(f"{ticker}: 未返回数据")
            continue
        record = result.records[0]
        market = market_for_asset_type(asset["asset_type"])
        closes = filter_settled_closes(record.get("recent_closes") or {}, market)
        parsed.append(AssetFetchRecord(asset, record, market, closes))
    return parsed, errors


def backfill_from_akshare(assets: list[dict[str, str]]) -> ClosesFetchResult:
    """为缺失资产批量拉取 AkShare 收盘价并写缓存，供 ensure 回填。"""
    errors: list[str] = []
    all_closes: dict[str, dict[str, float]] = {}
    parsed, parse_errors = parse_asset_fetch_results(assets, fetch_all_assets(assets))
    errors.extend(parse_errors)
    for row in parsed:
        ticker = row.asset["ticker"]
        if not row.closes:
            errors.append(f"{ticker}: 最近收盘价为空")
            continue
        all_closes[ticker] = row.closes
        write_price_cache(ticker, row.closes, market=row.market)
    latest = anchor_date_excluding_today(all_closes, markets=global_asset_markets(assets))
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return ClosesFetchResult(all_closes, errors)


def pending_item(asset: dict[str, str]) -> PriceLevelPendingItem:
    """构造数据待补齐资产的占位响应项。"""
    return PriceLevelPendingItem(
        ticker=asset["ticker"],
        name=asset["name"],
        asset_type=asset["asset_type"],
        conclusion="pending",
    )
