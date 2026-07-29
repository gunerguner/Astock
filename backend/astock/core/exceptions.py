from dataclasses import dataclass

from fastapi import status

from astock.core.error_codes import ErrorCode


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
