"""Redis 缓存 key 常量与工厂。"""


def price_key(ticker: str, date: str) -> str:
    return f"global_asset:price:{ticker}:{date}"


def recent_closes_key(ticker: str) -> str:
    return f"global_asset:recent:{ticker}"


LATEST_TRADING_DATE_KEY = "global_asset:meta:latest_trading_date"

MARKET_OVERVIEW_LATEST_DATE_KEY = "market_overview:meta:latest_trading_date"


def market_overview_recent_key(item_key: str) -> str:
    return f"market_overview:recent:{item_key}"


def market_overview_failure_key(item_key: str) -> str:
    return f"market_overview:failure:{item_key}"
