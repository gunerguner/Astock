from enum import Enum

from pydantic import BaseModel


class ImportDataset(str, Enum):
    turnover = "turnover"
    point = "point"
    stock = "stock"
    global_assets = "global_assets"
    all = "all"


class ImportResultItem(BaseModel):
    imported: int
    total: int
    last_date: str | None
    last_synced_at: str | None = None
    status: str
    source_errors: dict[str, str | None] | None = None
    elapsed: float | None = None


class ImportAllResult(BaseModel):
    turnover: ImportResultItem | None = None
    point: ImportResultItem | None = None
    stock: ImportResultItem | None = None
    global_assets: ImportResultItem | None = None
    status: str
