"""baostock 供应商适配。"""

from astock.providers.baostock.client import (
    BaostockQueryError,
    BaostockRecvTimeoutError,
    baostock_session,
    baostock_session_hold,
    login_error,
)

__all__ = [
    "BaostockQueryError",
    "BaostockRecvTimeoutError",
    "baostock_session",
    "baostock_session_hold",
    "login_error",
]
