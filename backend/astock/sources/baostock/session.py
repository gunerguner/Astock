"""baostock 会话管理与错误助手。"""

import logging
import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

import baostock as bs
import baostock.common.context as bs_context

from astock.config import BAOSTOCK_SOCKET_TIMEOUT
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 可重入会话：外层 hold 推迟 logout，嵌套 with 共享同一次 login。
_refcount = 0
_login_result: Any = None


class BaostockRecvTimeoutError(Exception):
    """baostock socket 接收超时或连接异常。"""


def configure_worker_socket() -> None:
    """ProcessPool worker 初始化：为 baostock 底层 socket 设置超时。"""
    sock = getattr(bs_context, "default_socket", None)
    if sock is not None:
        sock.settimeout(BAOSTOCK_SOCKET_TIMEOUT)


def _logout_if_idle() -> None:
    global _refcount, _login_result
    if _refcount == 0 and _login_result is not None:
        bs.logout()
        _login_result = None


@contextmanager
def baostock_session_hold() -> Iterator[None]:
    """推迟 logout：嵌套的 baostock_session 在 hold 退出前保持登录。

    本身不 login；若 hold 期间无人实际拉取，则不会触网。
    """
    global _refcount
    _refcount += 1
    try:
        yield
    finally:
        _refcount -= 1
        _logout_if_idle()


@contextmanager
def baostock_session():
    """baostock login 上下文；可重入，与 baostock_session_hold 共享引用计数。"""
    global _refcount, _login_result
    if _login_result is None:
        lg = bs.login()
        if lg.error_code == "0":
            configure_worker_socket()
        _login_result = lg
    _refcount += 1
    try:
        yield _login_result
    finally:
        _refcount -= 1
        _logout_if_idle()


def collect_rows(rs) -> list:
    """读取 ResultSet 全部行；socket 超时/连接异常时抛 BaostockRecvTimeoutError。"""
    try:
        return [rs.get_row_data() for _ in iter(rs.next, False)]
    except (socket.timeout, OSError) as e:
        raise BaostockRecvTimeoutError(str(e)) from e


def login_failure(lg) -> SourceFetchResult | None:
    if lg.error_code != "0":
        msg = f"baostock 登录失败: {lg.error_msg}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)
    return None


def query_failure(label: str, rs) -> SourceFetchResult | None:
    if rs.error_code != "0":
        msg = f"{label}: {rs.error_msg}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)
    return None


def _read_failure(label: str, exc: BaostockRecvTimeoutError) -> SourceFetchResult:
    msg = f"{label}: {exc}"
    logger.error(msg)
    return SourceFetchResult.failure(msg)


def safe_baostock_call[T](
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
