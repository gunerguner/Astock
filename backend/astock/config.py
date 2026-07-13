"""配置：环境变量（pydantic-settings）+ settings.yaml 常量 + 领域 YAML 懒加载。"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path(__file__).resolve().parent / "config"


@lru_cache
def _load_settings_yaml() -> dict[str, Any]:
    raw = yaml.safe_load((_CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _section(name: str) -> dict[str, Any]:
    section = _load_settings_yaml().get(name, {})
    return section if isinstance(section, dict) else {}


_cfg = _load_settings_yaml()
_business = _section("business")
_api = _section("api")
_batch = _section("batch")
_mappings = _section("mappings")
_baostock = _api.get("baostock", {})
_eastmoney = _api.get("eastmoney", {})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_path: str = "db/astock.db"
    fastapi_port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    redis_retry_cooldown: int = 60
    asset_price_cache_ttl: int = 86400
    market_overview_failure_ttl: int = 300
    log_level: str = "INFO"
    log_dir: str = "logs"
    cors_origins: list[str] = ["*"]
    host: str = "0.0.0.0"
    app_title: str = "Astock 数据平台"
    app_version: str = "1.0.0"
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]

    @field_validator("cors_origins", "cors_methods", "cors_headers", mode="before")
    @classmethod
    def split_csv_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()

# 向后兼容：保留模块级别名
DB_PATH = settings.db_path
DATABASE_URL = settings.database_url
FASTAPI_PORT = settings.fastapi_port
REDIS_URL = settings.redis_url
REDIS_RETRY_COOLDOWN = settings.redis_retry_cooldown
ASSET_PRICE_CACHE_TTL = settings.asset_price_cache_ttl
MARKET_OVERVIEW_FAILURE_TTL = settings.market_overview_failure_ttl
CORS_ORIGINS = settings.cors_origins
HOST = settings.host
APP_TITLE = settings.app_title
APP_VERSION = settings.app_version
CORS_METHODS = settings.cors_methods
CORS_HEADERS = settings.cors_headers

# business
TURNOVER_THRESHOLD = int(_business.get("turnover_threshold", 2_000_000_000_000))
STOCK_SLICE_TOP_N = int(_business.get("stock_slice_top_n", 20))
START_DATE = str(_business.get("start_date", "2005-01-01"))
GLOBAL_ASSET_RECENT_DAYS = 10
MARKET_OVERVIEW_RECENT_DAYS = int(_business.get("market_overview_recent_days", 10))
WEEKLY_BASELINE_OFFSET = int(_business.get("weekly_baseline_offset", 6))
PRICE_LEVEL_CONCLUSIONS: list[tuple[int, str]] = [
    (int(item[0]), str(item[1]))
    for item in _business.get(
        "price_level_conclusions",
        [(5, "nearAth"), (20, "moderatePullback"), (50, "significantPullback")],
    )
]
PRICE_LEVEL_DEFAULT = str(_business.get("price_level_default", "deepPullback"))

# batch
DEFAULT_UPSERT_BATCH_SIZE = int(_batch.get("default_upsert_batch_size", 500))
STOCK_UPSERT_FLUSH_SIZE = int(_batch.get("stock_upsert_flush_size", 5000))

# api
BAOSTOCK_SOCKET_TIMEOUT = int(_baostock.get("socket_timeout", 30))
EM_HIST_HOST = str(_eastmoney.get("hist_host", "https://push2his.eastmoney.com"))
EM_HIST_HOSTS: list[str] = [
    str(host)
    for host in _eastmoney.get(
        "hist_hosts",
        [EM_HIST_HOST, "https://88.push2his.eastmoney.com", "https://47.push2his.eastmoney.com"],
    )
]
EM_DELAY_HOST = str(_eastmoney.get("delay_host", "https://push2delay.eastmoney.com"))
EM_UDI_REFERER = "https://quote.eastmoney.com/gb/zsUDI.html"
EM_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
USD_HISTORY_TIMEOUT = int(_eastmoney.get("usd_history_timeout", 12))
USD_SPOT_TIMEOUT = int(_eastmoney.get("usd_spot_timeout", 15))
FETCH_RETRIES = int(_api.get("fetch_retries", 4))
FETCH_RETRY_DELAY = float(_api.get("fetch_retry_delay", 2.0))
CN_INDEX_LOOKBACK_DAYS = int(_api.get("cn_index_lookback_days", 180))

# mappings / filters
EXCHANGE_TURNOVER_CODES: dict[str, str] = dict(
    _mappings.get(
        "exchange_turnover_codes",
        {
            "sse_amount": "sh.000001",
            "szse_amount": "sz.399106",
        },
    )
)
US_BOND_COLUMNS: dict[str, str] = {
    "us_bond_5y": "美国国债收益率5年",
    "us_bond_10y": "美国国债收益率10年",
    "us_bond_30y": "美国国债收益率30年",
}
GLOBAL_INDEX_SINA_FALLBACK: dict[str, str] = {
    "道琼斯": ".DJI",
    "标普500": ".INX",
    "纳斯达克": ".IXIC",
}
STOCK_CODE_PREFIXES: dict[str, list[str]] = {
    "sh": ["60", "68"],
    "sz": ["00", "30"],
}


def point_sync_meta_key(index_code: str) -> str:
    """各指数点位同步水位在 sync_meta 中的 table_name。"""
    return f"point_{index_code}"


@lru_cache
def _load_point_index_config() -> dict[str, dict[str, str | float | int]]:
    raw = yaml.safe_load(
        (_CONFIG_DIR / "point_indices.yaml").read_text(encoding="utf-8")
    )
    return raw["point_indices"]


@lru_cache
def _load_bull_markets() -> dict[str, dict[str, str]]:
    raw = yaml.safe_load((_CONFIG_DIR / "bull_markets.yaml").read_text(encoding="utf-8"))
    return raw["bull_markets"]


@lru_cache
def _load_global_assets() -> list[dict[str, str]]:
    raw: dict[str, dict[str, str]] = yaml.safe_load(
        (_CONFIG_DIR / "global_assets.yaml").read_text(encoding="utf-8")
    )
    return [
        {"ticker": ticker, "name": name, "asset_type": asset_type}
        for asset_type, items in raw.items()
        for name, ticker in items.items()
    ]


@lru_cache
def _load_market_overview_categories() -> list[dict]:
    raw = yaml.safe_load((_CONFIG_DIR / "market_overview.yaml").read_text(encoding="utf-8"))
    return raw["categories"]


@lru_cache
def _load_market_overview_items() -> list[dict[str, str]]:
    return [
        {
            "key": f"{cat['key']}:{item['code']}",
            "category_key": cat["key"],
            "category_name": cat["display_name"],
            "name": item["name"],
            "code": item["code"],
            "source": item["source"],
        }
        for cat in _load_market_overview_categories()
        for item in cat["items"]
    ]


def __getattr__(name: str) -> Any:
    if name == "POINT_INDEX_CONFIG":
        return _load_point_index_config()
    if name == "THRESHOLD_POINT":
        return int(_load_point_index_config()["000001"]["default_threshold"])
    if name == "BULL_MARKETS":
        return _load_bull_markets()
    if name == "GLOBAL_ASSETS":
        return _load_global_assets()
    if name == "MARKET_OVERVIEW_CATEGORIES":
        return _load_market_overview_categories()
    if name == "MARKET_OVERVIEW_ITEMS":
        return _load_market_overview_items()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
