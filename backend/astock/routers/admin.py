from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from astock.core.deps import DbSession
from astock.schemas.imports import ImportDataset
from astock.schemas.response import success
from astock.services.import_service import get_sync_status, import_dataset, import_dataset_stream

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/data/import")
def trigger_import(db: DbSession, dataset: ImportDataset = ImportDataset.all):
    return success(import_dataset(db, dataset))


@router.post("/data/import/stream")
def trigger_import_stream(db: DbSession, dataset: ImportDataset = ImportDataset.all):
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
