"""个股日线历史并发拉取（ProcessPool + baostock）。"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections.abc import Iterator

import baostock as bs

from astock.config import STOCK_HISTORY_FETCH_WORKERS
from astock.services.imports.stock.context import StockImportContext
from astock.sources.baostock import configure_worker_socket, fetch_stock_amount_history
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _baostock_worker_init() -> None:
    """ProcessPool worker 初始化：每个子进程登录一次 baostock 会话。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock worker 登录失败: {lg.error_msg}")
    configure_worker_socket()


def _fetch_stock_amount_worker(
    task: tuple[str, str | None, str | None],
) -> tuple[str, SourceFetchResult]:
    code, start_date, end_date = task
    try:
        fr = fetch_stock_amount_history(code, start_date=start_date, end_date=end_date)
        return code, fr
    except Exception as e:
        return code, SourceFetchResult(records=[], ok=False, errors=[str(e)])


def iter_stock_history(
    ctx: StockImportContext,
) -> Iterator[tuple[int, str, SourceFetchResult]]:
    with ProcessPoolExecutor(
        max_workers=STOCK_HISTORY_FETCH_WORKERS,
        initializer=_baostock_worker_init,
    ) as executor:
        futures = {
            executor.submit(_fetch_stock_amount_worker, task): task[0]
            for task in ctx.tasks
        }
        for i, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            try:
                code, hist_fr = future.result()
            except Exception as e:
                msg = f"个股 {code} 处理异常: {e}"
                logger.warning(msg)
                ctx.stock_errors.append(msg)
                continue
            yield i, code, hist_fr
