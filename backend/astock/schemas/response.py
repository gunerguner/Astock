from typing import overload

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    code: int = 0
    message: str = "success"
    data: T | None = None


@overload
def success[T](data: T) -> ApiResponse[T]: ...


@overload
def success(data: None = None) -> ApiResponse[None]: ...


def success(data=None):
    return ApiResponse(code=0, message="success", data=data)


def error(message: str = "error", code: int = -1) -> ApiResponse[None]:
    return ApiResponse(code=code, message=message, data=None)
