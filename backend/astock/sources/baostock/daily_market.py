"""baostock 某日全市场 A 股日 K（0.9.3+ query_daily_history_k_AStock）。"""

import logging

import baostock as bs
import pandas as pd

from astock.sources.baostock.session import (
    query_failure,
    safe_baostock_call,
)
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.symbols import parse_baostock_code

logger = logging.getLogger(__name__)


def _parse_daily_amount_rows(rs) -> SourceFetchResult:
    rows = list(getattr(rs, "data", None) or [])
    fields = list(getattr(rs, "fields", None) or [])
    if not rows:
        return SourceFetchResult.empty()
    if "code" not in fields or "amount" not in fields:
        return SourceFetchResult.failure(f"全市场日K缺少字段: fields={fields}")

    code_idx = fields.index("code")
    amount_idx = fields.index("amount")
    records: list[dict] = []
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
        return SourceFetchResult.failure("全市场日K无有效成交额记录")
    return SourceFetchResult(records=records)


def fetch_daily_astock_amounts_logged_in(trade_date: str) -> SourceFetchResult:
    """已 login 的会话内拉取指定日全市场成交额。返回 ``{code, amount}``（元）。"""

    def _query() -> SourceFetchResult:
        rs = bs.query_daily_history_k_AStock(date=trade_date)
        if failed := query_failure(f"全市场日K失败({trade_date})", rs):
            return failed
        result = _parse_daily_amount_rows(rs)
        if not result.ok:
            if result.errors:
                return SourceFetchResult.failure(
                    f"{result.errors[0]}({trade_date})"
                )
            logger.info("全市场日K为空: %s", trade_date)
            return result
        if not result.records:
            logger.info("全市场日K为空: %s", trade_date)
            return result
        logger.info("全市场日K完成: date=%s stocks=%s", trade_date, len(result.records))
        return result

    return safe_baostock_call(f"全市场日K超时/连接异常({trade_date})", _query)
