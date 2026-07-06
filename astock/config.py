"""配置：环境变量 + 业务常量。"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "cache/astock.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", 8000))

# 默认阈值
THRESHOLD_POINT = 4000
TURNOVER_THRESHOLD = 2_000_000_000_000  # 默认2万亿

# 个股成交额配置
MARKET_CAP_THRESHOLD = 100_000_000_000  # 默认市值阈值1000亿（单位：元）
CANDIDATE_DAYS = 200  # 候选交易日数量
STOCK_TURNOVER_SLICE_THRESHOLD = 30_000_000_000  # 个股日成交额切片阈值，300亿

# 历史数据查询起始日期
START_DATE = "2005-01-01"

# 牛市时期定义（从 astock/config/bull_markets.yaml 加载）
_CONFIG_DIR = Path(__file__).resolve().parent / "config"
with open(_CONFIG_DIR / "bull_markets.yaml", "r", encoding="utf-8") as _f:
    BULL_MARKETS = yaml.safe_load(_f)["bull_markets"]
