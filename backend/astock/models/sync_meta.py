from sqlmodel import Field, SQLModel

from astock.core.sync_status import SyncStatus


class SyncMeta(SQLModel, table=True):
    __tablename__ = "sync_meta"

    table_name: str = Field(primary_key=True)
    last_synced_date: str | None = None
    last_synced_at: str | None = None
    last_status: SyncStatus | None = None
    last_error: str | None = None
