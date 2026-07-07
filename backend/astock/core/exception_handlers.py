import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from astock.core.error_codes import ErrorCode
from astock.core.exceptions import AppError, DatabaseAppError, ExternalSourceAppError
from astock.schemas.response import error

logger = logging.getLogger(__name__)


def _http_error_code(status_code: int) -> ErrorCode:
    match status_code:
        case 401 | 403:
            return ErrorCode.PERMISSION_DENIED
        case 404:
            return ErrorCode.RESOURCE_NOT_FOUND
        case 422:
            return ErrorCode.VALIDATION_ERROR
        case _:
            return ErrorCode.INTERNAL_ERROR


def _error_response(status_code: int, message: str, code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error(message=message, code=code).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExternalSourceAppError)
    async def external_source_error_handler(_: Request, exc: ExternalSourceAppError):
        logger.warning("external source failed: %s", exc.message)
        return _error_response(
            exc.status_code, exc.message, ErrorCode.EXTERNAL_SOURCE_ERROR
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return _error_response(exc.status_code, exc.message, exc.code)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_: Request, exc: RequestValidationError):
        logger.warning("request validation failed: %s", exc.errors())
        return _error_response(422, "参数校验失败", ErrorCode.VALIDATION_ERROR)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        code = _http_error_code(exc.status_code)
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_response(exc.status_code, detail, code)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(_: Request, exc: SQLAlchemyError):
        logger.exception("database operation failed")
        app_error = DatabaseAppError()
        return _error_response(
            app_error.status_code, app_error.message, ErrorCode.DATABASE_ERROR
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("unhandled exception")
        app_error = AppError(
            message="服务内部错误",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
        )
        return _error_response(app_error.status_code, app_error.message, app_error.code)
