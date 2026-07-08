"""全球市场概览数据源。"""

from astock.sources.market_overview.dispatcher import fetch_all_items, fetch_item_closes

__all__ = ["fetch_all_items", "fetch_item_closes"]
