"""akshare 数据源包：A股指数、全市场快照、全球资产。"""

from astock.sources.akshare.cn_index import fetch_cn_index_point
from astock.sources.akshare.global_asset import fetch_all_assets
from astock.sources.akshare.spot import fetch_stock_spot_snapshot

__all__ = [
    "fetch_cn_index_point",
    "fetch_stock_spot_snapshot",
    "fetch_all_assets",
]
