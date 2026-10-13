import hmac

from fastapi import APIRouter, Header, status
from fastapi.responses import StreamingResponse

from astock.config import settings
from astock.core.deps import DbSession
from astock.core.errors import AppError, ErrorCode
from astock.schemas.imports import ImportDataset
from astock.schemas.response import success
from astock.services.import_orchestrator import import_dataset_stream
from astock.services.sync.status import get_sync_status

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_admin_password(provided: str) -> None:
    expected = settings.admin_refresh_password
    if not expected:
        raise AppError(
            message="未配置刷新密码",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise AppError(
            message="密码错误",
            code=ErrorCode.PERMISSION_DENIED,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


@router.post("/data/import/stream")
def trigger_import_stream(
    db: DbSession,
    dataset: ImportDataset = ImportDataset.all,
    x_admin_password: str = Header(default="", alias="X-Admin-Password"),
):
    _require_admin_password(x_admin_password)
    return StreamingResponse(
        import_dataset_stream(db, dataset),
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
