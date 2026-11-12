"""个股名称解析：锚点日清单优先，缺口日补查。"""

import logging

from astock.datasets.result import FetchResult
from astock.datasets.stocks import fetch_all_stock_codes_logged_in
from astock.services.imports._common import is_missing_value

logger = logging.getLogger(__name__)


def names_from_fetch(fr: FetchResult) -> dict[str, str]:
    if not fr.ok:
        logger.warning("代码名称清单失败: %s", fr.error_summary())
        return {}
    return {
        str(r["code"]): str(r.get("name") or "")
        for r in fr.records
        if r.get("code")
    }


def resolve_name(
    code: str,
    trade_date: str,
    names: dict[str, str],
    day_names: dict[str, dict[str, str]],
) -> str:
    """先用截止日名称表，对不上再按该交易日查一次；仍没有则用代码占位。"""
    name = names.get(code, "")
    if not is_missing_value(name):
        return name
    if trade_date not in day_names:
        day_names[trade_date] = names_from_fetch(
            fetch_all_stock_codes_logged_in(trade_date)
        )
    name = day_names[trade_date].get(code, "")
    if is_missing_value(name):
        logger.warning("个股 %s@%s 缺少名称，用代码占位", code, trade_date)
        return code
    names[code] = name
    return name
