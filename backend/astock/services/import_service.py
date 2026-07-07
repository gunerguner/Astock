"""数据导入服务：增量拉取外部数据并写入 SQLite。"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Literal

import baostock as bs
import baostock.common.context as bs_context
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from astock.config import (
    MARKET_CAP_THRESHOLD,
    START_DATE,
    STOCK_HISTORY_FETCH_WORKERS,
    STOCK_TURNOVER_SLICE_THRESHOLD,
)
from astock.core.exceptions import ExternalSourceAppError
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.sync_meta import SyncMeta
from astock.models.turnover import Turnover
from astock.schemas.imports import ImportDataset
from astock.services.price_utils import iso_now
from astock.sources.baostock_client import (
    BaostockClient,
    _SOCKET_TIMEOUT_SECONDS,
    fetch_all_stock_codes,
    fetch_stock_amount_history,
)
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.tencent_client import TencentQuoteClient

logger = logging.getLogger(__name__)

baostock_client = BaostockClient()
tencent_client = TencentQuoteClient()

STOCK_UPSERT_FLUSH_SIZE = 5000
CommitMode = Literal["per_batch", "single"]


def _baostock_worker_init() -> None:
    """ProcessPool worker 初始化：每个子进程登录一次 baostock 会话。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock worker 登录失败: {lg.error_msg}")
    sock = getattr(bs_context, "default_socket", None)
    if sock is not None:
        sock.settimeout(_SOCKET_TIMEOUT_SECONDS)


def _fetch_stock_amount_worker(
    task: tuple[str, str | None],
) -> tuple[str, SourceFetchResult]:
    """在子进程中抓取单只股票历史成交额。"""
    code, start_date = task
    try:
        fr = fetch_stock_amount_history(code, start_date=start_date)
        return code, fr
    except Exception as e:
        return code, SourceFetchResult(records=[], ok=False, errors=[str(e)])


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
    synced_at = iso_now()
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
    *,
    batch_size: int = 500,
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


def _import_simple_dataset(
    db: Session,
    *,
    table_name: str,
    model: type,
    conflict_cols: list[str],
    fetch: Callable[[str], SourceFetchResult],
    source_key: str,
    failure_message: str,
    log_label: str,
) -> dict[str, Any]:
    start_ts = time.perf_counter()
    start_date = get_sync_start_date(db, table_name)

    fr = fetch(start_date)
    imported = _batch_upsert(
        db,
        model,
        fr.records,
        conflict_cols,
        commit_mode="single",
    )

    last_date = get_last_date(db, model)
    status = _resolve_status(fr.ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        table_name,
        last_synced_date=last_date,
        status=status,
        error=fr.error_summary() if not fr.ok else None,
    )

    result = _build_result(
        imported=imported,
        total=_count_rows(db, model),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map(source_key),
        last_synced_at=last_synced_at,
    )

    if result["status"] == "failed":
        raise ExternalSourceAppError(
            f"{failure_message}: {result['source_errors'].get(source_key)}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "%s导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        log_label,
        imported,
        result["total"],
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result


def import_turnover(db: Session) -> dict[str, Any]:
    return _import_simple_dataset(
        db,
        table_name="turnover",
        model=Turnover,
        conflict_cols=["date"],
        fetch=baostock_client.fetch_turnover,
        source_key="turnover",
        failure_message="成交额导入失败",
        log_label="成交额",
    )


def import_point(db: Session) -> dict[str, Any]:
    return _import_simple_dataset(
        db,
        table_name="point",
        model=Point,
        conflict_cols=["date"],
        fetch=baostock_client.fetch_point,
        source_key="point",
        failure_message="上证点位导入失败",
        log_label="上证点位",
    )


def import_stock(db: Session) -> dict[str, Any]:
    start_ts = time.perf_counter()
    errors: list[str] = []

    turnover_count = _count_rows(db, Turnover)
    if turnover_count == 0:
        import_turnover(db)

    meta = get_sync_meta(db, "stock_turnover")
    last_synced = meta.last_synced_date if meta else None

    as_of_date = get_last_date(db, Turnover)
    if as_of_date is None:
        raise ExternalSourceAppError("无法确定有效交易日：turnover 表为空")

    if last_synced and as_of_date <= last_synced:
        elapsed = time.perf_counter() - start_ts
        stock_last_date = get_last_date(db, StockTurnover)
        last_synced_at = upsert_sync_meta(
            db,
            "stock_turnover",
            last_synced_date=last_synced,
            status="success",
            error=None,
        )
        result = _build_result(
            imported=0,
            total=_count_rows(db, StockTurnover),
            last_date=stock_last_date,
            ok=True,
            source_errors={"stock": None},
            last_synced_at=last_synced_at,
        )
        result["elapsed"] = round(elapsed, 2)
        logger.info(
            "个股切片导入跳过: 无新交易日 (as_of=%s, last_synced=%s)",
            as_of_date,
            last_synced,
        )
        return result

    logger.info(
        "个股切片导入: as_of=%s, last_synced=%s, workers=%s",
        as_of_date,
        last_synced,
        STOCK_HISTORY_FETCH_WORKERS,
    )

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
    cached_at = iso_now()
    stock_errors: list[str] = []
    imported = 0
    record_buffer: list[dict[str, Any]] = []
    total_stocks = len(big_cap_codes)
    tasks = [(code, hist_start_date) for code in big_cap_codes]

    def flush_buffer() -> None:
        nonlocal imported, record_buffer
        if not record_buffer:
            return
        imported += _batch_upsert(
            db,
            StockTurnover,
            record_buffer,
            ["date", "code"],
            commit_mode="single",
        )
        record_buffer = []

    with ProcessPoolExecutor(
        max_workers=STOCK_HISTORY_FETCH_WORKERS,
        initializer=_baostock_worker_init,
    ) as executor:
        futures = {
            executor.submit(_fetch_stock_amount_worker, task): task[0]
            for task in tasks
        }
        for i, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            try:
                code, hist_fr = future.result()
            except Exception as e:
                msg = f"个股 {code} 处理异常: {e}"
                logger.warning(msg)
                stock_errors.append(msg)
                continue

            if not hist_fr.ok:
                stock_errors.extend(hist_fr.errors)
                continue

            name = code_to_name.get(code, "")
            record_buffer.extend(
                {
                    "date": row["date"],
                    "code": code,
                    "name": name,
                    "amount": row["amount"],
                    "cached_at": cached_at,
                }
                for row in hist_fr.records
                if row["amount"] >= STOCK_TURNOVER_SLICE_THRESHOLD
            )
            if len(record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
                flush_buffer()

            if i % 20 == 0:
                logger.info("个股日线进度: %s/%s", i, total_stocks)

    flush_buffer()

    all_errors = errors + stock_errors
    ok = len(all_errors) == 0
    status = _resolve_status(ok, imported)
    last_synced_at = upsert_sync_meta(
        db,
        "stock_turnover",
        last_synced_date=as_of_date,
        status=status,
        error="; ".join(all_errors[:5]) if all_errors else None,
    )

    result = _build_result(
        imported=imported,
        total=_count_rows(db, StockTurnover),
        last_date=as_of_date,
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


def import_global_assets(db: Session) -> dict[str, Any]:
    from astock.services.global_asset_service import refresh_asset_highs

    start_ts = time.perf_counter()
    result = refresh_asset_highs(db)
    elapsed = time.perf_counter() - start_ts
    result["elapsed"] = round(elapsed, 2)
    logger.info(
        "全球资产最高点刷新完成: imported=%s total=%s status=%s elapsed=%.2fs",
        result["imported"],
        result["total"],
        result["status"],
        elapsed,
    )
    return result


def _aggregate_status(*statuses: str) -> str:
    if all(s == "success" for s in statuses):
        return "success"
    if all(s == "failed" for s in statuses):
        return "failed"
    return "partial_failure"


_SYNC_STATUS_TABLES: dict[str, str] = {
    "turnover": "turnover",
    "point": "point",
    "stock_turnover": "stock",
    "asset_high": "global_assets",
}


def get_sync_status(db: Session) -> dict[str, Any]:
    """返回各数据集最近一次刷新的时间，供页面展示"最后更新时间"。"""
    status: dict[str, Any] = {}
    for table_name, dataset_key in _SYNC_STATUS_TABLES.items():
        meta = get_sync_meta(db, table_name)
        status[dataset_key] = {
            "last_synced_date": meta.last_synced_date if meta else None,
            "last_synced_at": meta.last_synced_at if meta else None,
            "status": meta.last_status if meta else None,
        }
    return status


def import_dataset(db: Session, dataset: ImportDataset) -> dict[str, Any]:
    match dataset:
        case ImportDataset.turnover:
            return import_turnover(db)
        case ImportDataset.point:
            return import_point(db)
        case ImportDataset.stock:
            return import_stock(db)
        case ImportDataset.global_assets:
            return import_global_assets(db)
        case ImportDataset.all:
            turnover_result = import_turnover(db)
            point_result = import_point(db)
            stock_result = import_stock(db)
            global_assets_result = import_global_assets(db)
            statuses = [
                turnover_result["status"],
                point_result["status"],
                stock_result["status"],
                global_assets_result["status"],
            ]
            return {
                "turnover": turnover_result,
                "point": point_result,
                "stock": stock_result,
                "global_assets": global_assets_result,
                "status": _aggregate_status(*statuses),
            }
