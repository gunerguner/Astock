"""baostock 个股代码与日线成交额。"""

import logging
import re

import baostock as bs

from astock.config import START_DATE
from astock.core.datetime_utils import today_local
from astock.sources.baostock.session import (
    _collect_rows,
    _login_failure,
    _query_failure,
    _safe_baostock_call,
    baostock_session,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^(sh|sz)\.(\d{6})$")


def _to_baostock_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}.{code}"


def fetch_all_stock_codes(as_of_date: str) -> SourceFetchResult:
    """全市场正常交易的沪深主板/中小板/创业板/科创板股票代码清单（不含指数/基金/B股）。

    用于个股大市值筛选的候选代码池，替代 akshare 实时快照里的代码来源。
    as_of_date 需为已知有效交易日（例如 turnover 表中的最新日期），
    baostock 若传入非交易日会返回空结果。
    """
    with baostock_session() as lg:
        if failed := _login_failure(lg):
            return failed

        rs = bs.query_all_stock(day=as_of_date)
        if failed := _query_failure("全市场代码清单查询失败", rs):
            return failed

        result = _safe_baostock_call(
            "全市场代码清单读取超时",
            lambda: _collect_rows(rs),
        )
        if isinstance(result, SourceFetchResult):
            return result
        rows = result

        records = []
        for code, status, name in rows:
            if status != "1":
                continue
            m = _CODE_RE.match(code)
            if not m:
                continue
            exchange, digits = m.groups()
            if exchange == "sh" and not digits.startswith(("60", "68")):
                continue
            if exchange == "sz" and not digits.startswith(("00", "30")):
                continue
            records.append({"code": digits, "name": name})

        logger.info("全市场股票代码清单获取完成: %s 只 (as_of=%s)", len(records), as_of_date)
        return SourceFetchResult(records=records)


def fetch_stock_amount_history(
    code: str, start_date: str | None = None
) -> SourceFetchResult:
    """获取单只股票日线成交额。调用方需已处于 baostock 登录会话中（见 baostock_session）。"""
    start = start_date or START_DATE
    prefixed = _to_baostock_code(code)

    def _query() -> SourceFetchResult:
        rs = bs.query_history_k_data_plus(
            prefixed,
            "date,amount",
            start_date=start,
            end_date=today_local(),
            frequency="d",
        )
        if failed := _query_failure(f"个股 {code} 日线查询失败", rs):
            return failed
        rows = _collect_rows(rs)
        records = [
            {"date": row[0], "amount": float(row[1])}
            for row in rows
            if row[1] not in ("", None)
        ]
        return SourceFetchResult(records=records)

    result = _safe_baostock_call(
        f"个股 {code} 日线查询超时/连接异常",
        _query,
        log_level="warning",
    )
    if isinstance(result, SourceFetchResult):
        return result
    return result
