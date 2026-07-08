"""同步状态查询。"""

from typing import Any

from sqlmodel import Session

from astock.config import POINT_INDEX_CONFIG, point_sync_meta_key
from astock.services.imports._common import aggregate_status
from astock.services.sync_store import get_sync_meta

_SYNC_STATUS_TABLES: dict[str, str] = {
    "turnover": "turnover",
    "point": "point",
    "stock_turnover": "stock",
    "asset_high": "global_assets",
}


def _get_point_sync_status(db: Session) -> dict[str, Any]:
    """聚合各指数点位同步状态，供页面展示。"""
    metas = []
    for index_code in POINT_INDEX_CONFIG:
        meta = get_sync_meta(db, point_sync_meta_key(index_code))
        if meta:
            metas.append(meta)

    legacy_meta = get_sync_meta(db, "point")
    if legacy_meta and not metas:
        metas.append(legacy_meta)

    if not metas:
        return {
            "last_synced_date": None,
            "last_synced_at": None,
            "status": None,
        }

    dates = [m.last_synced_date for m in metas if m.last_synced_date]
    synced_ats = [m.last_synced_at for m in metas if m.last_synced_at]
    statuses = [m.last_status for m in metas if m.last_status]

    return {
        "last_synced_date": max(dates) if dates else None,
        "last_synced_at": max(synced_ats) if synced_ats else None,
        "status": aggregate_status(*statuses) if statuses else None,
    }


def get_sync_status(db: Session) -> dict[str, Any]:
    """返回各数据集最近一次刷新的时间，供页面展示"最后更新时间"。"""
    status: dict[str, Any] = {}
    for table_name, dataset_key in _SYNC_STATUS_TABLES.items():
        if dataset_key == "point":
            status[dataset_key] = _get_point_sync_status(db)
            continue
        meta = get_sync_meta(db, table_name)
        status[dataset_key] = {
            "last_synced_date": meta.last_synced_date if meta else None,
            "last_synced_at": meta.last_synced_at if meta else None,
            "status": meta.last_status if meta else None,
        }
    return status
