import hmac

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse

from astock.config import settings
from astock.core.deps import DbSession
from astock.core.errors import AppError, ErrorCode
from astock.core.rate_limit import import_password_lock
from astock.schemas.imports import ImportDataset
from astock.schemas.response import success
from astock.services.import_orchestrator import end_import, import_dataset_stream, try_begin_import
from astock.services.sync.status import get_sync_status

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host


def _require_admin_password(provided: str, client: str) -> None:
    expected = settings.admin_refresh_password
    if not expected:
        raise AppError(
            message="未配置刷新密码",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    import_password_lock.check(client)
    if not provided or not hmac.compare_digest(provided, expected):
        import_password_lock.fail(client)
        raise AppError(
            message="密码错误",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    import_password_lock.success(client)


@router.post("/data/import/stream")
def trigger_import_stream(
    db: DbSession,
    request: Request,
    dataset: ImportDataset = ImportDataset.all,
    x_admin_password: str = Header(default="", alias="X-Admin-Password"),
):
    _require_admin_password(x_admin_password, _client_ip(request))
    if not try_begin_import():
        raise AppError(
            message="已有导入任务在执行",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_409_CONFLICT,
        )

    def guarded_stream():
        try:
            yield from import_dataset_stream(db, dataset)
        finally:
            end_import()

    return StreamingResponse(
        guarded_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/data/sync-status")
def sync_status(db: DbSession):
    return success(get_sync_status(db))
