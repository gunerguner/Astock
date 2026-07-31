"""统一业务错误码与业务异常。"""

from dataclasses import dataclass
from enum import IntEnum

from fastapi import status


class ErrorCode(IntEnum):
    VALIDATION_ERROR = 1001
    PERMISSION_DENIED = 1002
    RESOURCE_NOT_FOUND = 1003
    EXTERNAL_SOURCE_ERROR = 2001
    DATABASE_ERROR = 3001
    INTERNAL_ERROR = 9000


@dataclass(eq=False, kw_only=True)
class AppError(Exception):
    message: str = "服务内部错误"
    code: int = ErrorCode.INTERNAL_ERROR
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __post_init__(self) -> None:
        super().__init__(self.message)


@dataclass(eq=False, kw_only=True)
class ExternalSourceAppError(AppError):
    message: str = "外部数据源请求失败"
    code: int = ErrorCode.EXTERNAL_SOURCE_ERROR
    status_code: int = status.HTTP_502_BAD_GATEWAY


@dataclass(eq=False, kw_only=True)
class DatabaseAppError(AppError):
    message: str = "数据库操作失败"
    code: int = ErrorCode.DATABASE_ERROR
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
