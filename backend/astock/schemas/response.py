from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


def success(data: Any = None) -> ApiResponse[Any]:
    return ApiResponse(code=0, message="success", data=data)


def error(message: str = "error", code: int = -1) -> ApiResponse[Any]:
    return ApiResponse(code=code, message=message, data=None)
