"""baostock 会话管理与错误助手。"""

import logging
import socket
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

import baostock as bs
import baostock.common.context as bs_context

from astock.config import BAOSTOCK_SOCKET_TIMEOUT
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaostockRecvTimeoutError(Exception):
    """baostock socket 接收超时或连接异常。"""


def configure_worker_socket() -> None:
    """ProcessPool worker 初始化：为 baostock 底层 socket 设置超时。"""
    sock = getattr(bs_context, "default_socket", None)
    if sock is not None:
        sock.settimeout(BAOSTOCK_SOCKET_TIMEOUT)


@contextmanager
def baostock_session():
    lg = bs.login()
    if lg.error_code == "0":
        configure_worker_socket()
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


def _login_failure(lg) -> SourceFetchResult | None:
    if lg.error_code != "0":
        msg = f"baostock 登录失败: {lg.error_msg}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)
    return None


def _query_failure(label: str, rs) -> SourceFetchResult | None:
    if rs.error_code != "0":
        msg = f"{label}: {rs.error_msg}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)
    return None


def _read_failure(label: str, exc: BaostockRecvTimeoutError) -> SourceFetchResult:
    msg = f"{label}: {exc}"
    logger.error(msg)
    return SourceFetchResult.failure(msg)


def _safe_baostock_call[T](
    label: str,
    fn: Callable[[], T],
    *,
    log_level: str = "error",
) -> T | SourceFetchResult:
    try:
        return fn()
    except (socket.timeout, OSError) as e:
        msg = f"{label}: {e}"
        getattr(logger, log_level)(msg)
        return SourceFetchResult.failure(msg)
    except BaostockRecvTimeoutError as e:
        return _read_failure(label, e)
