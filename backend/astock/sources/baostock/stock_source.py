"""baostock 全市场股票代码清单。"""

import logging

import baostock as bs

from astock.config import STOCK_CODE_PREFIXES
from astock.sources.baostock.session import (
    collect_rows,
    query_failure,
    safe_baostock_call,
)
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.symbols import parse_baostock_code

logger = logging.getLogger(__name__)


def _parse_stock_code_rows(rows: list) -> list[dict]:
    records = []
    for code, status, name in rows:
        if status != "1":
            continue
        parsed = parse_baostock_code(code)
        if not parsed:
            continue
        exchange, digits = parsed
        prefixes = tuple(STOCK_CODE_PREFIXES.get(exchange, ()))
        if prefixes and not digits.startswith(prefixes):
            continue
        records.append({"code": digits, "name": name})
    return records


def fetch_all_stock_codes_logged_in(as_of_date: str) -> SourceFetchResult:
    """已 login 的会话内拉取股票代码+名称清单。"""
    rs = bs.query_all_stock(day=as_of_date)
    if failed := query_failure("全市场代码清单查询失败", rs):
        return failed

    result = safe_baostock_call(
        "全市场代码清单读取超时",
        lambda: collect_rows(rs),
    )
    if isinstance(result, SourceFetchResult):
        return result

    records = _parse_stock_code_rows(result)
    logger.info("全市场股票代码清单获取完成: %s 只 (as_of=%s)", len(records), as_of_date)
    return SourceFetchResult(records=records)
