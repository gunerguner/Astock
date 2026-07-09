"""akshare 数据源包：A股指数、全市场快照、全球资产。"""

from astock.sources.akshare.cn_index import fetch_cn_index_daily_raw, fetch_cn_index_point
from astock.sources.akshare.global_asset import (
    extract_ath,
    extract_recent_closes,
    fetch_all_assets,
    fetch_asset_history,
    fetch_commodity_history,
    fetch_one_asset,
    fetch_stock_history,
)
from astock.sources.akshare.spot import fetch_stock_spot_snapshot

__all__ = [
    "fetch_cn_index_daily_raw",
    "fetch_cn_index_point",
    "fetch_stock_spot_snapshot",
    "fetch_stock_history",
    "fetch_commodity_history",
    "fetch_asset_history",
    "extract_ath",
    "extract_recent_closes",
    "fetch_one_asset",
    "fetch_all_assets",
]
