"""baostock 个股原始查询：代码清单、全市场日成交。"""

from __future__ import annotations

import logging

import baostock as bs
import pandas as pd

from astock.config import STOCK_CODE_PREFIXES
from astock.providers._shared.symbols import parse_baostock_code
from astock.providers.baostock.client import (
    BaostockQueryError,
    collect_rows,
    query_error,
    safe_baostock_call,
)

logger = logging.getLogger(__name__)


def query_all_stock_codes(as_of_date: str) -> list[dict[str, str]]:
    """已 login 的会话内拉取股票代码+名称清单。"""
    rs = bs.query_all_stock(day=as_of_date)
    if err := query_error("全市场代码清单查询失败", rs):
        raise BaostockQueryError(err)

    rows = safe_baostock_call(
        "全市场代码清单读取超时",
        lambda: collect_rows(rs),
    )
    records: list[dict[str, str]] = []
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
    logger.info("全市场股票代码清单获取完成: %s 只 (as_of=%s)", len(records), as_of_date)
    return records


def query_daily_astock_amounts(trade_date: str) -> list[dict[str, float | str]]:
    """已 login 的会话内拉取指定日全市场成交额。返回 ``{code, amount}``（元）。"""

    def _query() -> list[dict[str, float | str]]:
        rs = bs.query_daily_history_k_AStock(date=trade_date)
        if err := query_error(f"全市场日K失败({trade_date})", rs):
            raise BaostockQueryError(err)

        rows = list(getattr(rs, "data", None) or [])
        fields = list(getattr(rs, "fields", None) or [])
        if not rows:
            logger.info("全市场日K为空: %s", trade_date)
            return []
        if "code" not in fields or "amount" not in fields:
            raise BaostockQueryError(f"全市场日K缺少字段: fields={fields}({trade_date})")

        code_idx = fields.index("code")
        amount_idx = fields.index("amount")
        records: list[dict[str, float | str]] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) <= max(code_idx, amount_idx):
                continue
            parsed = parse_baostock_code(str(row[code_idx]).strip())
            if not parsed:
                raw = str(row[code_idx]).strip()
                digits = raw.split(".")[-1] if "." in raw else raw
                if len(digits) != 6 or not digits.isdigit():
                    continue
                code = digits
            else:
                code = parsed[1]
            amount = pd.to_numeric(row[amount_idx], errors="coerce")
            if pd.isna(amount):
                continue
            records.append({"code": code, "amount": float(amount)})

        if not records:
            raise BaostockQueryError(f"全市场日K无有效成交额记录({trade_date})")
        logger.info("全市场日K完成: date=%s stocks=%s", trade_date, len(records))
        return records

    return safe_baostock_call(f"全市场日K超时/连接异常({trade_date})", _query)
