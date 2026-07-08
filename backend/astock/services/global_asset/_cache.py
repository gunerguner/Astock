"""全球资产价格缓存读写。"""

from astock.config import ASSET_PRICE_CACHE_TTL, PRICE_LEVEL_CONCLUSIONS, PRICE_LEVEL_DEFAULT
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
from astock.services.price_utils import (
    latest_trading_date,
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


def write_price_cache(ticker: str, closes: dict[str, float]) -> None:
    if not closes:
        return
    sorted_items = sorted(closes.items())
    for d, price in sorted_items:
        set_string(price_key(ticker, d), str(price), ttl=ASSET_PRICE_CACHE_TTL)
    write_recent_closes_cache(
        set_json,
        recent_closes_key(ticker),
        closes,
        ttl=ASSET_PRICE_CACHE_TTL,
    )


def read_price_cache(ticker: str) -> dict[str, float]:
    closes = read_recent_closes_cache(get_json, recent_closes_key(ticker))
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
        closes = record.get("recent_closes") or {}
        if not closes:
            errors.append(f"{ticker}: 最近收盘价为空")
            continue
        all_closes[ticker] = closes
        write_price_cache(ticker, closes)
    latest = latest_trading_date(all_closes)
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
