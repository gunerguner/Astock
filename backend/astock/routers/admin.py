from fastapi import APIRouter

from astock.core.decorators import handle_success_response
from astock.core.deps import DbSession
from astock.schemas.imports import ImportDataset
from astock.services.import_service import get_sync_status, import_dataset

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/data/import")
@handle_success_response
def trigger_import(db: DbSession, dataset: ImportDataset = ImportDataset.all):
    return import_dataset(db, dataset)


@router.get("/data/sync-status")
@handle_success_response
def sync_status(db: DbSession):
    return get_sync_status(db)
