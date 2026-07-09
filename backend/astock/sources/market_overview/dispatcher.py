"""全球市场概览数据源路由分发。"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from astock.config import MARKET_OVERVIEW_RECENT_DAYS
from astock.sources.market_overview.boc_forex import fetch_boc_forex
from astock.sources.market_overview.cn_index import fetch_cn_index
from astock.sources.market_overview.foreign_futures import fetch_foreign_futures
from astock.sources.market_overview.global_index import fetch_global_index
from astock.sources.market_overview.us_bond import fetch_us_bond_rates

logger = logging.getLogger(__name__)
_FETCH_WORKERS = 4


def fetch_item_closes(item: dict[str, str], n: int = MARKET_OVERVIEW_RECENT_DAYS) -> dict[str, float]:
    source = item["source"]
    code = item["code"]
    if source == "global_index":
        return fetch_global_index(code, n)
    if source == "cn_index":
        return fetch_cn_index(code, n)
    if source == "foreign_futures":
        return fetch_foreign_futures(code, n)
    if source == "boc_forex":
        return fetch_boc_forex(code, n)
    if source == "us_bond":
        return {}
    logger.warning("未知 source: %s", source)
    return {}


def fetch_all_items(
    items: list[dict[str, str]],
    n: int = MARKET_OVERVIEW_RECENT_DAYS,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """串行抓取全部资产，返回 {item_key: recent_closes} 与错误列表。"""
    all_closes: dict[str, dict[str, float]] = {}
    errors: list[str] = []

    us_bond_items = [it for it in items if it["source"] == "us_bond"]
    other_items = [it for it in items if it["source"] != "us_bond"]

    if us_bond_items:
        bond_rates = fetch_us_bond_rates()
        for item in us_bond_items:
            key = item["key"]
            closes = bond_rates.get(item["code"], {})
            if closes:
                all_closes[key] = closes
            else:
                errors.append(f"{item['name']}({item['code']}): 美债数据为空")

    def _fetch_one(item: dict[str, str]) -> tuple[str, dict[str, float], str | None]:
        key = item["key"]
        try:
            closes = fetch_item_closes(item, n)
            if closes:
                return key, closes, None
            return key, {}, f"{item['name']}({item['code']}): 数据为空"
        except Exception as e:
            logger.warning("抓取 %s 失败: %s", key, e)
            return key, {}, f"{item['name']}({item['code']}): {e}"

    if other_items:
        workers = min(_FETCH_WORKERS, len(other_items))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_fetch_one, item) for item in other_items]
            for future in as_completed(futures):
                key, closes, err = future.result()
                if closes:
                    all_closes[key] = closes
                elif err:
                    errors.append(err)

    return all_closes, errors
