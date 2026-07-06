"""baostock 指数/个股数据客户端。"""

import logging
import re
import socket
from contextlib import contextmanager
from datetime import datetime

import baostock as bs
import baostock.common.context as bs_context
import pandas as pd

from astock.config import START_DATE
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^(sh|sz)\.(\d{6})$")

# baostock 底层 socket 默认无超时（阻塞模式）：一旦服务端在传输中途失联，
# recv() 会永久阻塞。登录后主动设置超时，避免单次请求卡死整个导入流程。
_SOCKET_TIMEOUT_SECONDS = 30


class BaostockRecvTimeoutError(Exception):
    """baostock socket 接收超时或连接异常。"""


@contextmanager
def baostock_session():
    lg = bs.login()
    if lg.error_code == "0":
        sock = getattr(bs_context, "default_socket", None)
        if sock is not None:
            sock.settimeout(_SOCKET_TIMEOUT_SECONDS)
    try:
        yield lg
    finally:
        bs.logout()


def _collect_rows(rs) -> list:
    """读取 ResultSet 全部行；socket 超时/连接异常时抛 BaostockRecvTimeoutError。"""
    try:
        return [rs.get_row_data() for _ in iter(rs.next, False)]
    except (socket.timeout, OSError) as e:
        raise BaostockRecvTimeoutError(str(e)) from e


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
        if lg.error_code != "0":
            msg = f"baostock 登录失败: {lg.error_msg}"
            logger.error(msg)
            return SourceFetchResult(records=[], ok=False, errors=[msg])

        rs = bs.query_all_stock(day=as_of_date)
        if rs.error_code != "0":
            msg = f"全市场代码清单查询失败: {rs.error_msg}"
            logger.error(msg)
            return SourceFetchResult(records=[], ok=False, errors=[msg])

        try:
            rows = _collect_rows(rs)
        except BaostockRecvTimeoutError as e:
            msg = f"全市场代码清单读取超时: {e}"
            logger.error(msg)
            return SourceFetchResult(records=[], ok=False, errors=[msg])

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
    try:
        rs = bs.query_history_k_data_plus(
            prefixed,
            "date,amount",
            start_date=start,
            end_date=_today(),
            frequency="d",
        )
    except (socket.timeout, OSError) as e:
        msg = f"个股 {code} 日线查询超时/连接异常: {e}"
        logger.warning(msg)
        return SourceFetchResult(records=[], ok=False, errors=[msg])

    if rs.error_code != "0":
        msg = f"个股 {code} 日线查询失败: {rs.error_msg}"
        return SourceFetchResult(records=[], ok=False, errors=[msg])

    try:
        rows = _collect_rows(rs)
    except BaostockRecvTimeoutError as e:
        msg = f"个股 {code} 日线读取超时/连接异常: {e}"
        logger.warning(msg)
        return SourceFetchResult(records=[], ok=False, errors=[msg])

    records = [
        {"date": row[0], "amount": float(row[1])}
        for row in rows
        if row[1] not in ("", None)
    ]
    return SourceFetchResult(records=records)


class BaostockClient:
    def fetch_point(self, start_date: str | None = None) -> SourceFetchResult:
        start = start_date or START_DATE
        end = _today()
        errors: list[str] = []

        with baostock_session() as lg:
            if lg.error_code != "0":
                msg = f"baostock 登录失败: {lg.error_msg}"
                logger.error(msg)
                return SourceFetchResult(records=[], ok=False, errors=[msg])

            try:
                rs = bs.query_history_k_data_plus(
                    "sh.000001",
                    "date,close",
                    start_date=start,
                    end_date=end,
                    frequency="d",
                )
            except (socket.timeout, OSError) as e:
                msg = f"上证点位查询超时/连接异常: {e}"
                logger.error(msg)
                return SourceFetchResult(records=[], ok=False, errors=[msg])

            if rs.error_code != "0":
                msg = f"上证点位查询失败: {rs.error_msg}"
                logger.error(msg)
                return SourceFetchResult(records=[], ok=False, errors=[msg])

            try:
                rows = _collect_rows(rs)
            except BaostockRecvTimeoutError as e:
                msg = f"上证点位读取超时/连接异常: {e}"
                logger.error(msg)
                return SourceFetchResult(records=[], ok=False, errors=[msg])

            if not rows:
                logger.info("上证点位无新增数据: %s → %s", start, end)
                return SourceFetchResult()

            df = pd.DataFrame(rows, columns=rs.fields)
            df["close"] = df["close"].astype(float)
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

            cached_at = _iso_now()
            records = [
                {"date": row["date"], "close": row["close"], "cached_at": cached_at}
                for row in df.to_dict("records")
            ]
            logger.info("上证点位拉取完成: %s 条 (%s → %s)", len(records), start, end)
            return SourceFetchResult(records=records, ok=len(errors) == 0, errors=errors)

    def fetch_turnover(self, start_date: str | None = None) -> SourceFetchResult:
        start = start_date or START_DATE
        end = _today()
        errors: list[str] = []

        index_codes = {
            "sh_amount": "sh.000001",
            "sz_amount": "sz.399001",
            "cyb_amount": "sz.399006",
        }

        with baostock_session() as lg:
            if lg.error_code != "0":
                msg = f"baostock 登录失败: {lg.error_msg}"
                logger.error(msg)
                return SourceFetchResult(records=[], ok=False, errors=[msg])

            all_records: list[pd.DataFrame] = []
            for col_name, code in index_codes.items():
                try:
                    rs = bs.query_history_k_data_plus(
                        code,
                        "date,amount",
                        start_date=start,
                        end_date=end,
                        frequency="d",
                    )
                except (socket.timeout, OSError) as e:
                    msg = f"{col_name} 查询超时/连接异常: {e}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

                if rs.error_code != "0":
                    msg = f"{col_name} 查询失败: {rs.error_msg}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

                try:
                    rows = _collect_rows(rs)
                except BaostockRecvTimeoutError as e:
                    msg = f"{col_name} 读取超时/连接异常: {e}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

                if not rows:
                    continue

                df = pd.DataFrame(rows, columns=rs.fields)
                df["amount"] = df["amount"].astype(float)
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                df.rename(columns={"amount": col_name}, inplace=True)
                all_records.append(df[["date", col_name]])

            if not all_records:
                if errors:
                    return SourceFetchResult(records=[], ok=False, errors=errors)
                logger.info("成交额无新增数据: %s → %s", start, end)
                return SourceFetchResult()

            merged = pd.concat(all_records, axis=0).groupby("date", as_index=False).sum()
            for col in ["sh_amount", "sz_amount", "cyb_amount"]:
                if col not in merged.columns:
                    merged[col] = 0.0

            merged["turnover"] = merged[["sh_amount", "sz_amount", "cyb_amount"]].sum(axis=1)
            merged = merged.sort_values("date")

            cached_at = _iso_now()
            records = [
                {
                    "date": row["date"],
                    "sh_amount": row["sh_amount"],
                    "sz_amount": row["sz_amount"],
                    "cyb_amount": row["cyb_amount"],
                    "turnover": row["turnover"],
                    "cached_at": cached_at,
                }
                for row in merged.to_dict("records")
            ]
            logger.info("成交额拉取完成: %s 条 (%s → %s)", len(records), start, end)
            return SourceFetchResult(records=records, ok=len(errors) == 0, errors=errors)
