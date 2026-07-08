"""数据导入服务：增量拉取外部数据并写入 SQLite。"""

import logging
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

import baostock as bs
import baostock.common.context as bs_context
from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import (
    MARKET_CAP_THRESHOLD,
    POINT_INDEX_CONFIG,
    START_DATE,
    STOCK_HISTORY_FETCH_WORKERS,
    STOCK_TURNOVER_SLICE_THRESHOLD,
    point_sync_meta_key,
)
from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.core.sync_status import SyncStatus
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.schemas.imports import ImportDataset
from astock.services.global_asset_service import refresh_asset_highs
from astock.services.price_utils import iso_now
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_meta,
    get_sync_start_date,
    upsert_sync_meta,
)
from astock.sources.akshare_client import fetch_cn_index_point
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

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "point": ["index_code", "close", "cached_at"],
    "turnover": ["sh_amount", "sz_amount", "cyb_amount", "turnover", "cached_at"],
    "stock_turnover": ["name", "amount", "cached_at"],
}


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _filter_required_records(
    records: list[dict[str, Any]],
    required_fields: list[str],
    label: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    for record in records:
        missing = [field for field in required_fields if _is_missing_value(record.get(field))]
        if missing:
            identity = record.get("date") or record.get("code") or "unknown"
            errors.append(f"{label}: 缺失字段 {','.join(missing)} ({identity})")
            continue
        valid.append(record)
    return valid, errors


def _prepare_records_for_upsert(
    table_name: str,
    records: list[dict[str, Any]],
    *,
    fr: SourceFetchResult,
) -> list[dict[str, Any]]:
    required_fields = _REQUIRED_FIELDS.get(table_name)
    if not required_fields:
        return records
    valid_records, filter_errors = _filter_required_records(
        records,
        required_fields,
        table_name,
    )
    if filter_errors:
        fr.errors.extend(filter_errors)
        fr.ok = False
    return valid_records


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


def _resolve_status(ok: bool, imported: int) -> SyncStatus:
    if ok:
        return SyncStatus.SUCCESS
    if imported > 0:
        return SyncStatus.PARTIAL_FAILURE
    return SyncStatus.FAILED


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
    records = _prepare_records_for_upsert(table_name, fr.records, fr=fr)
    imported = batch_upsert(
        db,
        model,
        records,
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
        total=count_rows(db, model),
        last_date=last_date,
        ok=fr.ok,
        source_errors=fr.to_error_map(source_key),
        last_synced_at=last_synced_at,
    )

    if result["status"] == SyncStatus.FAILED:
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


def _fetch_point_index(index_code: str, start_date: str) -> SourceFetchResult:
    config = POINT_INDEX_CONFIG[index_code]
    source = str(config.get("source", "baostock"))
    if source == "akshare":
        return fetch_cn_index_point(index_code, start_date=start_date)
    return baostock_client.fetch_point(index_code=index_code, start_date=start_date)


def import_point(db: Session) -> dict[str, Any]:
    start_ts = time.perf_counter()
    total_imported = 0
    total_rows = count_rows(db, Point)
    all_errors: list[str] = []
    source_errors: dict[str, str | None] = {}
    last_dates: list[str] = []
    last_synced_ats: list[str] = []
    statuses: list[SyncStatus] = []

    for index_code, config in POINT_INDEX_CONFIG.items():
        index_name = str(config["name"])
        table_name = point_sync_meta_key(index_code)
        start_date = get_sync_start_date(db, table_name)

        fr = _fetch_point_index(index_code, start_date)
        records = _prepare_records_for_upsert("point", fr.records, fr=fr)
        imported = batch_upsert(
            db,
            Point,
            records,
            ["date", "index_code"],
            commit_mode="single",
        )

        last_date = db.exec(
            select(func.max(Point.date)).where(Point.index_code == index_code)
        ).one()
        status = _resolve_status(fr.ok, imported)
        last_synced_at = upsert_sync_meta(
            db,
            table_name,
            last_synced_date=last_date,
            status=status,
            error=fr.error_summary() if not fr.ok else None,
        )

        total_imported += imported
        total_rows = count_rows(db, Point)
        statuses.append(status)
        if last_date:
            last_dates.append(last_date)
        if last_synced_at:
            last_synced_ats.append(last_synced_at)
        if not fr.ok:
            all_errors.append(f"{index_name}: {fr.error_summary()}")
        source_errors[index_code] = fr.error_summary() if not fr.ok else None

        logger.info(
            "%s点位导入: imported=%s status=%s",
            index_name,
            imported,
            status,
        )

    ok = len(all_errors) == 0
    aggregate_status = _aggregate_status(*statuses)
    result = _build_result(
        imported=total_imported,
        total=total_rows,
        last_date=max(last_dates) if last_dates else None,
        ok=ok,
        source_errors=source_errors if source_errors else None,
        last_synced_at=max(last_synced_ats) if last_synced_ats else None,
    )
    result["status"] = aggregate_status

    if result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"指数点位导入失败: {'; '.join(all_errors[:5])}"
        )

    elapsed = time.perf_counter() - start_ts
    logger.info(
        "指数点位导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
        total_imported,
        total_rows,
        result["status"],
        elapsed,
    )
    result["elapsed"] = round(elapsed, 2)
    return result


def import_stock(
    db: Session,
    on_progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    gen = _import_stock_gen(db, on_progress=on_progress)
    try:
        while True:
            next(gen)
    except StopIteration as exc:
        return exc.value


def _import_stock_gen(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
):
    start_ts = time.perf_counter()
    errors: list[str] = []

    turnover_count = count_rows(db, Turnover)
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
            status=SyncStatus.SUCCESS,
            error=None,
        )
        result = _build_result(
            imported=0,
            total=count_rows(db, StockTurnover),
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
        imported += batch_upsert(
            db,
            StockTurnover,
            record_buffer,
            ["date", "code"],
            commit_mode="single",
        )
        record_buffer = []

    def emit_stock_progress(current: int):
        if on_progress is None:
            return
        on_progress.phase_progress(
            "stock",
            current,
            total_stocks,
            f"个股日线 {current}/{total_stocks}",
            imported=imported,
        )
        if bridge is not None:
            yield from bridge.drain()

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
            if _is_missing_value(name):
                stock_errors.append(f"个股 {code}: 缺少股票名称")
                continue

            record_buffer.extend(
                {
                    "date": row["date"],
                    "code": code,
                    "name": name,
                    "amount": row["amount"],
                    "cached_at": cached_at,
                }
                for row in hist_fr.records
                if not _is_missing_value(row.get("amount"))
                and row["amount"] >= STOCK_TURNOVER_SLICE_THRESHOLD
            )
            if len(record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
                flush_buffer()

            if i % 20 == 0:
                logger.info("个股日线进度: %s/%s", i, total_stocks)
                yield from emit_stock_progress(i)
            elif i % 100 == 0 and on_progress is not None:
                on_progress.ping()
                if bridge is not None:
                    yield from bridge.drain()

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
        total=count_rows(db, StockTurnover),
        last_date=as_of_date,
        ok=ok,
        source_errors={"stock": "; ".join(all_errors[:5]) if all_errors else None},
        last_synced_at=last_synced_at,
    )

    if result["status"] == SyncStatus.FAILED:
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


def _aggregate_status(*statuses: SyncStatus | str) -> SyncStatus:
    if all(s == SyncStatus.SUCCESS for s in statuses):
        return SyncStatus.SUCCESS
    if all(s == SyncStatus.FAILED for s in statuses):
        return SyncStatus.FAILED
    return SyncStatus.PARTIAL_FAILURE


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
        "status": _aggregate_status(*statuses) if statuses else None,
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


def import_dataset(
    db: Session,
    dataset: ImportDataset,
    on_progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    def run_phase(key: str, fn: Callable[[Session], dict[str, Any]]) -> dict[str, Any]:
        if on_progress:
            on_progress.phase_start(key)
        result = fn(db)
        if on_progress:
            on_progress.phase_done(key, result)
        return result

    match dataset:
        case ImportDataset.turnover:
            return run_phase("turnover", import_turnover)
        case ImportDataset.point:
            return run_phase("point", import_point)
        case ImportDataset.stock:
            if on_progress:
                on_progress.phase_start("stock")
            result = import_stock(db, on_progress=on_progress)
            if on_progress:
                on_progress.phase_done("stock", result)
            return result
        case ImportDataset.global_assets:
            return run_phase("global_assets", import_global_assets)
        case ImportDataset.all:
            turnover_result = run_phase("turnover", import_turnover)
            point_result = run_phase("point", import_point)
            if on_progress:
                on_progress.phase_start("stock")
            stock_result = import_stock(db, on_progress=on_progress)
            if on_progress:
                on_progress.phase_done("stock", stock_result)
            global_assets_result = run_phase("global_assets", import_global_assets)
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


def _stream_run_phase(
    db: Session,
    key: str,
    fn: Callable[[Session], dict[str, Any]],
    reporter: ProgressReporter,
    bridge: SSEBridge,
) -> Iterator[str]:
    reporter.phase_start(key)
    yield from bridge.drain()
    result = fn(db)
    reporter.phase_done(key, result)
    yield from bridge.drain()
    return result


def _stream_stock_phase(
    db: Session,
    reporter: ProgressReporter,
    bridge: SSEBridge,
) -> Iterator[str]:
    reporter.phase_start("stock")
    yield from bridge.drain()
    stock_gen = _import_stock_gen(db, on_progress=reporter, bridge=bridge)
    try:
        while True:
            yield next(stock_gen)
    except StopIteration as exc:
        stock_result = exc.value
    reporter.phase_done("stock", stock_result)
    yield from bridge.drain()
    return stock_result


def import_dataset_stream(
    db: Session,
    dataset: ImportDataset,
) -> Iterator[str]:
    bridge = SSEBridge()
    reporter = ProgressReporter(bridge.emit)

    try:
        match dataset:
            case ImportDataset.turnover:
                result = yield from _stream_run_phase(
                    db, "turnover", import_turnover, reporter, bridge
                )
            case ImportDataset.point:
                result = yield from _stream_run_phase(
                    db, "point", import_point, reporter, bridge
                )
            case ImportDataset.stock:
                result = yield from _stream_stock_phase(db, reporter, bridge)
            case ImportDataset.global_assets:
                result = yield from _stream_run_phase(
                    db, "global_assets", import_global_assets, reporter, bridge
                )
            case ImportDataset.all:
                turnover_result = yield from _stream_run_phase(
                    db, "turnover", import_turnover, reporter, bridge
                )
                point_result = yield from _stream_run_phase(
                    db, "point", import_point, reporter, bridge
                )
                stock_result = yield from _stream_stock_phase(db, reporter, bridge)
                global_assets_result = yield from _stream_run_phase(
                    db, "global_assets", import_global_assets, reporter, bridge
                )
                result = {
                    "turnover": turnover_result,
                    "point": point_result,
                    "stock": stock_result,
                    "global_assets": global_assets_result,
                    "status": _aggregate_status(
                        turnover_result["status"],
                        point_result["status"],
                        stock_result["status"],
                        global_assets_result["status"],
                    ),
                }
            case _:
                raise ValueError(f"unsupported dataset: {dataset}")

        reporter.done(result)
        yield from bridge.drain()
    except Exception as exc:
        logger.exception("流式导入失败")
        reporter.error(str(exc))
        yield from bridge.drain()
