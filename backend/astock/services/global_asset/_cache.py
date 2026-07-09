"""全球资产价格缓存读写。"""

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS, PRICE_LEVEL_CONCLUSIONS, PRICE_LEVEL_DEFAULT
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
from astock.core.datetime_utils import filter_settled_closes, market_for_asset_type
from astock.services.price_utils import (
    anchor_date_excluding_today,
    global_asset_markets,
    read_recent_closes_cache,
    write_recent_closes_cache,
)
from astock.sources.akshare_client import fetch_all_assets

def conclusion(percentage_diff: float) -> str:
    abs_diff = abs(percentage_diff)
    for threshold, label in PRICE_LEVEL_CONCLUSIONS:
        if abs_diff < threshold:
            return label
    return PRICE_LEVEL_DEFAULT


def write_price_cache(ticker: str, closes: dict[str, float], *, market: str) -> None:
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
    closes = read_recent_closes_cache(get_json, recent_closes_key(ticker), market=market)
    if closes:
        return closes

    latest = get_string(LATEST_TRADING_DATE_KEY)
    if latest:
        raw = get_string(price_key(ticker, latest))
        if raw is not None:
            return {latest: float(raw)}
    return {}


def backfill_from_akshare(
    assets: list[dict[str, str]],
) -> tuple[dict[str, dict[str, float]], list[str]]:
    errors: list[str] = []
    all_closes: dict[str, dict[str, float]] = {}
    fetch_results = fetch_all_assets(assets)
    for asset in assets:
        ticker = asset["ticker"]
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
        if not closes:
            errors.append(f"{ticker}: 最近收盘价为空")
            continue
        all_closes[ticker] = closes
        write_price_cache(ticker, closes, market=market)
    latest = anchor_date_excluding_today(all_closes, markets=global_asset_markets(assets))
    if latest:
        set_string(LATEST_TRADING_DATE_KEY, latest, ttl=ASSET_PRICE_CACHE_TTL)
    return all_closes, errors


def pending_item(asset: dict[str, str]) -> PriceLevelPendingItem:
    return PriceLevelPendingItem(
        ticker=asset["ticker"],
        name=asset["name"],
        asset_type=asset["asset_type"],
        conclusion="pending",
    )
