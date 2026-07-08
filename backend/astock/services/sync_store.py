"""增量同步水位与 SQLite 批量 upsert 共用工具。"""

from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from astock.config import DEFAULT_UPSERT_BATCH_SIZE, START_DATE
from astock.core.sync_status import SyncStatus
from astock.models.sync_meta import SyncMeta
from astock.services.price_utils import iso_now

CommitMode = Literal["per_batch", "single"]


def get_last_date(db: Session, model: type) -> str | None:
    return db.exec(select(func.max(model.date))).one()


def get_sync_meta(db: Session, table_name: str) -> SyncMeta | None:
    return db.exec(
        select(SyncMeta).where(SyncMeta.table_name == table_name)
    ).first()


def get_sync_start_date(db: Session, table_name: str) -> str:
    meta = get_sync_meta(db, table_name)
    if meta and meta.last_synced_date:
        return meta.last_synced_date
    return START_DATE


def upsert_sync_meta(
    db: Session,
    table_name: str,
    *,
    last_synced_date: str | None,
    status: SyncStatus | str,
    error: str | None = None,
) -> str:
    meta = get_sync_meta(db, table_name) or SyncMeta(table_name=table_name)
    synced_at = iso_now()
    meta.last_synced_date = last_synced_date
    meta.last_synced_at = synced_at
    meta.last_status = status
    meta.last_error = error
    db.merge(meta)
    db.commit()
    return synced_at


def count_rows(db: Session, model: type) -> int:
    return db.exec(select(func.count()).select_from(model)).one()


def batch_upsert(
    db: Session,
    model: type,
    records: list[dict[str, Any]],
    conflict_cols: list[str],
    *,
    batch_size: int = DEFAULT_UPSERT_BATCH_SIZE,
    commit_mode: CommitMode = "per_batch",
) -> int:
    if not records:
        return 0

    total = 0
    table = model.__table__
    try:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = sqlite_insert(table).values(batch)
            update_cols = {
                col.name: stmt.excluded[col.name]
                for col in table.columns
                if col.name not in conflict_cols
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_cols,
                set_=update_cols,
            )
            db.exec(stmt)
            if commit_mode == "per_batch":
                db.commit()
            total += len(batch)
        if commit_mode == "single":
            db.commit()
    except Exception:
        db.rollback()
        raise
    return total
