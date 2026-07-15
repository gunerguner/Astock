"""全球市场概览数据源路由分发。"""

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from astock.config import MARKET_OVERVIEW_RECENT_DAYS
from astock.services.closes_cache import ClosesFetchResult
from astock.sources.market_overview.boc_forex import fetch_boc_forex
from astock.sources.market_overview.cn_index import fetch_cn_index
from astock.sources.market_overview.foreign_futures import fetch_foreign_futures
from astock.sources.market_overview.global_index import fetch_global_index
from astock.sources.market_overview.us_bond import fetch_us_bond_rates

logger = logging.getLogger(__name__)

# Linux 生产可并行；macOS 上 akshare mini_racer/V8 并发会 FATAL
_PARALLEL_MAX_WORKERS = 4


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


def _fetch_one_other(item: dict[str, str], n: int) -> tuple[str, dict[str, float] | None, str | None]:
    """抓取单项非美债；返回 (key, closes|None, error|None)。"""
    key = item["key"]
    started = time.perf_counter()
    try:
        closes = fetch_item_closes(item, n)
        elapsed = time.perf_counter() - started
        if closes:
            logger.info(
                "概览外网抓取成功: key=%s source=%s elapsed=%.2fs",
                key,
                item["source"],
                elapsed,
            )
            return key, closes, None
        err = f"{item['name']}({item['code']}): 数据为空"
        logger.warning(
            "概览外网抓取空: key=%s source=%s elapsed=%.2fs",
            key,
            item["source"],
            elapsed,
        )
        return key, None, err
    except Exception as e:
        elapsed = time.perf_counter() - started
        logger.warning(
            "概览外网抓取失败: key=%s source=%s elapsed=%.2fs err=%s",
            key,
            item["source"],
            elapsed,
            e,
        )
        return key, None, f"{item['name']}({item['code']}): {e}"


def _fetch_other_items_serial(
    other_items: list[dict[str, str]],
    n: int,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    all_closes: dict[str, dict[str, float]] = {}
    errors: list[str] = []
    for item in other_items:
        key, closes, err = _fetch_one_other(item, n)
        if closes:
            all_closes[key] = closes
        if err:
            errors.append(err)
    return all_closes, errors


def _fetch_other_items_parallel(
    other_items: list[dict[str, str]],
    n: int,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    all_closes: dict[str, dict[str, float]] = {}
    errors: list[str] = []
    workers = min(_PARALLEL_MAX_WORKERS, len(other_items))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_one_other, item, n): item for item in other_items}
        for fut in as_completed(futures):
            key, closes, err = fut.result()
            if closes:
                all_closes[key] = closes
            if err:
                errors.append(err)
    return all_closes, errors


def fetch_all_items(
    items: list[dict[str, str]],
    n: int = MARKET_OVERVIEW_RECENT_DAYS,
) -> ClosesFetchResult:
    """抓取全部资产：美债一次批量，其余按平台串行或并行。

    macOS：故意串行——akshare（mini_racer/V8）并发初始化会 FATAL
    ``address_pool_manager``。Linux 生产用小线程池缩短墙钟时间。
    """
    all_closes: dict[str, dict[str, float]] = {}
    errors: list[str] = []
    batch_started = time.perf_counter()

    us_bond_items = [it for it in items if it["source"] == "us_bond"]
    other_items = [it for it in items if it["source"] != "us_bond"]

    if us_bond_items:
        bond_started = time.perf_counter()
        bond_rates = fetch_us_bond_rates()
        bond_elapsed = time.perf_counter() - bond_started
        logger.info("概览美债批量抓取 elapsed=%.2fs keys=%d", bond_elapsed, len(us_bond_items))
        for item in us_bond_items:
            key = item["key"]
            closes = bond_rates.get(item["code"], {})
            if closes:
                all_closes[key] = closes
            else:
                errors.append(f"{item['name']}({item['code']}): 美债数据为空")

    if other_items:
        use_parallel = sys.platform != "darwin" and len(other_items) > 1
        if use_parallel:
            logger.info(
                "概览外网并行抓取: platform=%s workers=%d items=%d",
                sys.platform,
                min(_PARALLEL_MAX_WORKERS, len(other_items)),
                len(other_items),
            )
            part_closes, part_errors = _fetch_other_items_parallel(other_items, n)
        else:
            logger.info(
                "概览外网串行抓取: platform=%s items=%d",
                sys.platform,
                len(other_items),
            )
            part_closes, part_errors = _fetch_other_items_serial(other_items, n)
        all_closes.update(part_closes)
        errors.extend(part_errors)

    logger.info(
        "概览外网批次结束: ok=%d errors=%d elapsed=%.2fs",
        len(all_closes),
        len(errors),
        time.perf_counter() - batch_started,
    )
    return ClosesFetchResult(all_closes, errors)
