"""配置：环境变量 + 业务常量。"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "db/astock.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", 8000))

# 默认阈值
THRESHOLD_POINT = 4000
TURNOVER_THRESHOLD = 2_000_000_000_000  # 默认2万亿

# 个股成交额配置
MARKET_CAP_THRESHOLD = 100_000_000_000  # 默认市值阈值1000亿（单位：元）
STOCK_TURNOVER_SLICE_THRESHOLD = 30_000_000_000  # 个股日成交额切片阈值，300亿
STOCK_HISTORY_FETCH_WORKERS = 4  # 个股历史抓取并发进程数

# 历史数据查询起始日期
START_DATE = "2005-01-01"

# 牛市时期定义（从 astock/config/bull_markets.yaml 加载）
_CONFIG_DIR = Path(__file__).resolve().parent / "config"
with open(_CONFIG_DIR / "bull_markets.yaml", "r", encoding="utf-8") as _f:
    BULL_MARKETS = yaml.safe_load(_f)["bull_markets"]

# 全球资产价格水位
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ASSET_PRICE_CACHE_TTL = int(os.getenv("ASSET_PRICE_CACHE_TTL", "86400"))
GLOBAL_ASSET_RECENT_DAYS = 10
GLOBAL_ASSET_FETCH_WORKERS = int(os.getenv("GLOBAL_ASSET_FETCH_WORKERS", "8"))

with open(_CONFIG_DIR / "global_assets.yaml", "r", encoding="utf-8") as _f:
    _GLOBAL_ASSETS_RAW: dict[str, dict[str, str]] = yaml.safe_load(_f)

GLOBAL_ASSETS: list[dict[str, str]] = [
    {"ticker": ticker, "name": name, "asset_type": asset_type}
    for asset_type, items in _GLOBAL_ASSETS_RAW.items()
    for name, ticker in items.items()
]

# 全球市场概览
MARKET_OVERVIEW_RECENT_DAYS = 10
MARKET_OVERVIEW_FAILURE_TTL = int(os.getenv("MARKET_OVERVIEW_FAILURE_TTL", "300"))

with open(_CONFIG_DIR / "market_overview.yaml", "r", encoding="utf-8") as _f:
    _MARKET_OVERVIEW_RAW: dict = yaml.safe_load(_f)

MARKET_OVERVIEW_CATEGORIES: list[dict] = _MARKET_OVERVIEW_RAW["categories"]

MARKET_OVERVIEW_ITEMS: list[dict[str, str]] = [
    {
        "key": f"{cat['key']}:{item['code']}",
        "category_key": cat["key"],
        "category_name": cat["display_name"],
        "name": item["name"],
        "code": item["code"],
        "source": item["source"],
    }
    for cat in MARKET_OVERVIEW_CATEGORIES
    for item in cat["items"]
]
