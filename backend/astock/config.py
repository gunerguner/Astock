"""配置：环境变量（pydantic-settings）+ 业务常量 + YAML 懒加载。"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path(__file__).resolve().parent / "config"


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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()

# 向后兼容：保留模块级别名，旧 `from astock.config import XXX` 无需改动
DB_PATH = settings.db_path
DATABASE_URL = settings.database_url
FASTAPI_PORT = settings.fastapi_port
REDIS_URL = settings.redis_url
REDIS_RETRY_COOLDOWN = settings.redis_retry_cooldown
ASSET_PRICE_CACHE_TTL = settings.asset_price_cache_ttl
MARKET_OVERVIEW_FAILURE_TTL = settings.market_overview_failure_ttl
CORS_ORIGINS = settings.cors_origins

# 默认阈值（非 env）
THRESHOLD_POINT = 4000
TURNOVER_THRESHOLD = 2_000_000_000_000  # 默认2万亿

# 个股成交额配置
MARKET_CAP_THRESHOLD = 100_000_000_000  # 默认市值阈值1000亿（单位：元）
STOCK_TURNOVER_SLICE_THRESHOLD = 30_000_000_000  # 个股日成交额切片阈值，300亿
STOCK_HISTORY_FETCH_WORKERS = 4  # 个股历史抓取并发进程数

# 历史数据查询起始日期
START_DATE = "2005-01-01"

GLOBAL_ASSET_RECENT_DAYS = 10
MARKET_OVERVIEW_RECENT_DAYS = 10


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
    if name == "BULL_MARKETS":
        return _load_bull_markets()
    if name == "GLOBAL_ASSETS":
        return _load_global_assets()
    if name == "MARKET_OVERVIEW_CATEGORIES":
        return _load_market_overview_categories()
    if name == "MARKET_OVERVIEW_ITEMS":
        return _load_market_overview_items()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
