"""数据导入服务：增量拉取外部数据并写入 SQLite。"""

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from astock.config import (
    CANDIDATE_DAYS,
    MARKET_CAP_THRESHOLD,
    START_DATE,
    STOCK_TURNOVER_SLICE_THRESHOLD,
)
from astock.core.exceptions import ExternalSourceAppError
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.sync_meta import SyncMeta
from astock.models.turnover import Turnover
from astock.schemas.imports import ImportDataset
from astock.sources.baostock_client import (
    BaostockClient,
    baostock_session,
    fetch_all_stock_codes,
    fetch_stock_amount_history,
)
from astock.sources.tencent_client import TencentQuoteClient

logger = logging.getLogger(__name__)

baostock_client = BaostockClient()
tencent_client = TencentQuoteClient()


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    status: str,
    error: str | None = None,
) -> str:
    meta = get_sync_meta(db, table_name) or SyncMeta(table_name=table_name)
    synced_at = _iso_now()
    meta.last_synced_date = last_synced_date
    meta.last_synced_at = synced_at
    meta.last_status = status
    meta.last_error = error
    db.merge(meta)
    db.commit()
    return synced_at


def _count_rows(db: Session, model: type) -> int:
    return db.exec(select(func.count()).select_from(model)).one()


def _batch_upsert(
    db: Session,
    model: type,
    records: list[dict[str, Any]],
    conflict_cols: list[str],
    batch_size: int = 500,
) -> int:
    if not records:
        return 0

    total = 0
    table = model.__table__
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
        db.commit()
        total += len(batch)
    return total


def _resolve_status(ok: bool, imported: int) -> str:
    if ok:
        return "success"
    if imported > 0:
        return "partial_failure"
    return "failed"


def _build_result(
    *,
    imported: int,
    total: int,
    last_date: str | None,
    ok: bool,
    source_errors: dict[str, str | None] | None = None,
    last_synced_at: str | None = None,
) -> dict[str, Any]:
    status = _resolve_status(ok, imported)
    return {
        "imported": imported,
        "total": total,
        "last_date": last_date,
        "last_synced_at": last_synced_at,
        "status": status,
        "source_errors": source_errors,
    }


def import_turnover(db: Session) -> dict[str, Any]:
    start_ts = time.perf_counter()
    start_date = get_sync_start_date(db, "turnover")

    fr = baostock_client.fetch_turnover(start_date)
    imported = _batch_upsert(db, Turnover, fr.records, ["date"])

    last_date = get_last_date(db, Turnover)
    status = _resolve_status(fr.ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        "turnover",
        last_synced_date=last_date,
        status=status,
        error=fr.error_summary() if not fr.ok else None,
    )

    result = _build_result(
        imported=imported,
        total=_count_rows(db, Turnover),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map("turnover"),
        last_synced_at=last_synced_at,
    )

    if result["status"] == "failed":
        raise ExternalSourceAppError(
            f"成交额导入失败: {result['source_errors'].get('turnover')}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "成交额导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        imported,
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result


def import_point(db: Session) -> dict[str, Any]:
    start_ts = time.perf_counter()
    start_date = get_sync_start_date(db, "point")

    fr = baostock_client.fetch_point(start_date)
    imported = _batch_upsert(db, Point, fr.records, ["date"])

    last_date = get_last_date(db, Point)
    status = _resolve_status(fr.ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        "point",
        last_synced_date=last_date,
        status=status,
        error=fr.error_summary() if not fr.ok else None,
    )

    result = _build_result(
        imported=imported,
        total=_count_rows(db, Point),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map("point"),
        last_synced_at=last_synced_at,
    )

    if result["status"] == "failed":
        raise ExternalSourceAppError(
            f"上证点位导入失败: {result['source_errors'].get('point')}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "上证点位导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        imported,
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result


def import_stock(db: Session) -> dict[str, Any]:
    start_ts = time.perf_counter()
    errors: list[str] = []

    turnover_count = _count_rows(db, Turnover)
    if turnover_count == 0:
        import_turnover(db)

    meta = get_sync_meta(db, "stock_turnover")
    last_synced = meta.last_synced_date if meta else None

    turnover_query = select(Turnover).order_by(desc(Turnover.turnover))
    if last_synced:
        turnover_query = turnover_query.where(Turnover.date > last_synced)
    turnover_rows = db.exec(turnover_query.limit(CANDIDATE_DAYS)).all()
    candidate_dates = {row.date for row in turnover_rows}

    cached_dates = set(db.exec(select(StockTurnover.date).distinct()).all())
    new_candidate_dates = candidate_dates - cached_dates

    logger.info(
        "个股切片导入: 候选日 %s, 已缓存 %s, 新增 %s, last_synced=%s",
        len(candidate_dates),
        len(cached_dates & candidate_dates),
        len(new_candidate_dates),
        last_synced,
    )

    if not new_candidate_dates:
        elapsed = time.perf_counter() - start_ts
        last_date = get_last_date(db, StockTurnover)
        last_synced_at = upsert_sync_meta(
            db,
            "stock_turnover",
            last_synced_date=last_date,
            status="success",
            error=None,
        )
        result = _build_result(
            imported=0,
            total=_count_rows(db, StockTurnover),
            last_date=last_date,
            ok=True,
            source_errors={"stock": None},
            last_synced_at=last_synced_at,
        )
        result["elapsed"] = round(elapsed, 2)
        return result

    as_of_date = get_last_date(db, Turnover)
    if as_of_date is None:
        raise ExternalSourceAppError("无法确定有效交易日：turnover 表为空")
    codes_fr = fetch_all_stock_codes(as_of_date)
    if not codes_fr.ok or not codes_fr.records:
        raise ExternalSourceAppError(
            f"全市场代码清单获取失败: {codes_fr.error_summary()}"
        )

    code_to_name = {r["code"]: r["name"] for r in codes_fr.records}
    caps_fr = tencent_client.fetch_market_caps(list(code_to_name.keys()))
    if not caps_fr.ok and not caps_fr.records:
        raise ExternalSourceAppError(f"股票市值快照失败: {caps_fr.error_summary()}")
    if not caps_fr.ok:
        errors.extend(caps_fr.errors)

    big_cap_codes = [
        r["code"] for r in caps_fr.records if r["market_cap"] > MARKET_CAP_THRESHOLD
    ]
    logger.info(
        "大市值股票筛选完成: %s 只 (阈值 %.0f 亿)",
        len(big_cap_codes),
        MARKET_CAP_THRESHOLD / 1e8,
    )

    hist_start_date = last_synced or START_DATE
    cached_at = _iso_now()
    slice_records: list[dict[str, Any]] = []
    stock_errors: list[str] = []

    with baostock_session() as lg:
        if lg.error_code != "0":
            raise ExternalSourceAppError(f"baostock 登录失败: {lg.error_msg}")

        total_stocks = len(big_cap_codes)
        for i, code in enumerate(big_cap_codes):
            name = code_to_name.get(code, "")
            hist_fr = fetch_stock_amount_history(code, start_date=hist_start_date)
            if not hist_fr.ok:
                stock_errors.extend(hist_fr.errors)
                continue

            for row in hist_fr.records:
                if row["date"] not in new_candidate_dates:
                    continue
                if row["amount"] < STOCK_TURNOVER_SLICE_THRESHOLD:
                    continue
                slice_records.append(
                    {
                        "date": row["date"],
                        "code": code,
                        "name": name,
                        "amount": row["amount"],
                        "cached_at": cached_at,
                    }
                )

            if (i + 1) % 20 == 0:
                logger.info("个股日线进度: %s/%s", i + 1, total_stocks)

    imported = _batch_upsert(db, StockTurnover, slice_records, ["date", "code"])
    all_errors = errors + stock_errors
    ok = len(all_errors) == 0
    last_date = get_last_date(db, StockTurnover)
    status = _resolve_status(ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        "stock_turnover",
        last_synced_date=last_date,
        status=status,
        error="; ".join(all_errors[:5]) if all_errors else None,
    )

    result = _build_result(
        imported=imported,
        total=_count_rows(db, StockTurnover),
        last_date=last_date,
        ok=ok,
        source_errors={"stock": "; ".join(all_errors[:5]) if all_errors else None},
        last_synced_at=last_synced_at,
    )

    if result["status"] == "failed":
        raise ExternalSourceAppError(
            f"个股切片导入失败: {result['source_errors'].get('stock')}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "个股切片导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        imported,
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result


def _aggregate_status(*statuses: str) -> str:
    if all(s == "success" for s in statuses):
        return "success"
    if all(s == "failed" for s in statuses):
        return "failed"
    return "partial_failure"


def import_dataset(db: Session, dataset: ImportDataset) -> dict[str, Any]:
    match dataset:
        case ImportDataset.turnover:
            return import_turnover(db)
        case ImportDataset.point:
            return import_point(db)
        case ImportDataset.stock:
            return import_stock(db)
        case ImportDataset.all:
            turnover_result = import_turnover(db)
            point_result = import_point(db)
            stock_result = import_stock(db)
            statuses = [
                turnover_result["status"],
                point_result["status"],
                stock_result["status"],
            ]
            return {
                "turnover": turnover_result,
                "point": point_result,
                "stock": stock_result,
                "status": _aggregate_status(*statuses),
            }
