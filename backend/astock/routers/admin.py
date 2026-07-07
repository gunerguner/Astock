from fastapi import APIRouter

from astock.core.deps import DbSession
from astock.schemas.imports import ImportDataset
from astock.schemas.response import success
from astock.services.import_service import get_sync_status, import_dataset

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/data/import")
def trigger_import(db: DbSession, dataset: ImportDataset = ImportDataset.all):
    return success(import_dataset(db, dataset))


@router.get("/data/sync-status")
def sync_status(db: DbSession):
    return success(get_sync_status(db))
