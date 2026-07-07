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
class ValidationAppError(AppError):
    message: str = "参数校验失败"
    code: int = ErrorCode.VALIDATION_ERROR
    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY


@dataclass(eq=False, kw_only=True)
class PermissionAppError(AppError):
    message: str = "权限不足"
    code: int = ErrorCode.PERMISSION_DENIED
    status_code: int = status.HTTP_403_FORBIDDEN


@dataclass(eq=False, kw_only=True)
class NotFoundAppError(AppError):
    message: str = "资源不存在"
    code: int = ErrorCode.RESOURCE_NOT_FOUND
    status_code: int = status.HTTP_404_NOT_FOUND


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
