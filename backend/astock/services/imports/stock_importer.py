"""个股切片数据导入。"""

import logging
import time
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import baostock as bs

from sqlmodel import Session

from astock.config import (
    MARKET_CAP_THRESHOLD,
    START_DATE,
    STOCK_HISTORY_FETCH_WORKERS,
    STOCK_TURNOVER_SLICE_THRESHOLD,
)
from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.core.sync_status import SyncStatus
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports._common import build_result, is_missing_value, resolve_status
from astock.services.imports.turnover_importer import import_turnover
from astock.services.price_utils import iso_now
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.sources.baostock import (
    configure_worker_socket,
    fetch_all_stock_codes,
    fetch_stock_amount_history,
)
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.tencent_client import TencentQuoteClient

logger = logging.getLogger(__name__)

STOCK_UPSERT_FLUSH_SIZE = 5000

tencent_client = TencentQuoteClient()


def _baostock_worker_init() -> None:
    """ProcessPool worker 初始化：每个子进程登录一次 baostock 会话。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock worker 登录失败: {lg.error_msg}")
    configure_worker_socket()


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


@dataclass
class StockImportContext:
    db: Session
    on_progress: ProgressReporter | None = None
    bridge: SSEBridge | None = None
    start_ts: float = field(default_factory=time.perf_counter)
    is_skipped: bool = False
    errors: list[str] = field(default_factory=list)
    stock_errors: list[str] = field(default_factory=list)
    imported: int = 0
    record_buffer: list[dict[str, Any]] = field(default_factory=list)
    code_to_name: dict[str, str] = field(default_factory=dict)
    big_cap_codes: list[str] = field(default_factory=list)
    total_stocks: int = 0
    tasks: list[tuple[str, str | None]] = field(default_factory=list)
    as_of_date: str | None = None
    hist_start_date: str = START_DATE
    cached_at: str = ""

    def build_skip_result(self) -> dict[str, Any]:
        elapsed = time.perf_counter() - self.start_ts
        stock_last_date = get_last_date(self.db, StockTurnover)
        meta = get_sync_meta(self.db, "stock_turnover")
        last_synced = meta.last_synced_date if meta else None
        last_synced_at = upsert_sync_meta(
            self.db,
            "stock_turnover",
            last_synced_date=last_synced,
            status=SyncStatus.SUCCESS,
            error=None,
        )
        result = build_result(
            imported=0,
            total=count_rows(self.db, StockTurnover),
            last_date=stock_last_date,
            ok=True,
            source_errors={"stock": None},
            last_synced_at=last_synced_at,
        )
        result["elapsed"] = round(elapsed, 2)
        logger.info(
            "个股切片导入跳过: 无新交易日 (as_of=%s, last_synced=%s)",
            self.as_of_date,
            last_synced,
        )
        return result

    def flush_buffer(self) -> None:
        if not self.record_buffer:
            return
        self.imported += batch_upsert(
            self.db,
            StockTurnover,
            self.record_buffer,
            ["date", "code"],
            commit_mode="single",
        )
        self.record_buffer = []

    def emit_stock_progress(self, current: int) -> Iterator[str]:
        if self.on_progress is not None:
            self.on_progress.phase_progress(
                "stock",
                current,
                self.total_stocks,
                f"个股日线 {current}/{self.total_stocks}",
                imported=self.imported,
            )
        if self.bridge is not None:
            yield from self.bridge.drain()

    def accumulate(self, code: str, hist_fr: SourceFetchResult) -> None:
        if not hist_fr.ok:
            self.stock_errors.extend(hist_fr.errors)
            return

        name = self.code_to_name.get(code, "")
        if is_missing_value(name):
            self.stock_errors.append(f"个股 {code}: 缺少股票名称")
            return

        self.record_buffer.extend(
            {
                "date": row["date"],
                "code": code,
                "name": name,
                "amount": row["amount"],
                "cached_at": self.cached_at,
            }
            for row in hist_fr.records
            if not is_missing_value(row.get("amount"))
            and row["amount"] >= STOCK_TURNOVER_SLICE_THRESHOLD
        )

    def maybe_flush(self) -> None:
        if len(self.record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
            self.flush_buffer()

    def build_result(self) -> dict[str, Any]:
        all_errors = self.errors + self.stock_errors
        ok = len(all_errors) == 0
        status = resolve_status(ok, self.imported)
        last_synced_at = upsert_sync_meta(
            self.db,
            "stock_turnover",
            last_synced_date=self.as_of_date,
            status=status,
            error="; ".join(all_errors[:5]) if all_errors else None,
        )

        result = build_result(
            imported=self.imported,
            total=count_rows(self.db, StockTurnover),
            last_date=self.as_of_date,
            ok=ok,
            source_errors={"stock": "; ".join(all_errors[:5]) if all_errors else None},
            last_synced_at=last_synced_at,
        )

        if result["status"] == SyncStatus.FAILED:
            raise ExternalSourceAppError(
                f"个股切片导入失败: {result['source_errors'].get('stock')}"
            )

        elapsed = time.perf_counter() - self.start_ts
        logger.info(
            "个股切片导入完成: imported=%s total=%s status=%s elapsed=%.2fs",
            self.imported,
            result["total"],
            result["status"],
            elapsed,
        )
        result["elapsed"] = round(elapsed, 2)
        return result


def _init_stock_context(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
) -> StockImportContext:
    ctx = StockImportContext(db=db, on_progress=on_progress, bridge=bridge)

    turnover_count = count_rows(db, Turnover)
    if turnover_count == 0:
        import_turnover(db)

    meta = get_sync_meta(db, "stock_turnover")
    last_synced = meta.last_synced_date if meta else None

    as_of_date = get_last_date(db, Turnover)
    if as_of_date is None:
        raise ExternalSourceAppError("无法确定有效交易日：turnover 表为空")

    if last_synced and as_of_date <= last_synced:
        ctx.is_skipped = True
        ctx.as_of_date = as_of_date
        return ctx

    ctx.as_of_date = as_of_date
    ctx.hist_start_date = last_synced or START_DATE
    ctx.cached_at = iso_now()

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

    ctx.code_to_name = {r["code"]: r["name"] for r in codes_fr.records}
    caps_fr = tencent_client.fetch_market_caps(list(ctx.code_to_name.keys()))
    if not caps_fr.ok and not caps_fr.records:
        raise ExternalSourceAppError(f"股票市值快照失败: {caps_fr.error_summary()}")
    if not caps_fr.ok:
        ctx.errors.extend(caps_fr.errors)

    ctx.big_cap_codes = [
        r["code"] for r in caps_fr.records if r["market_cap"] > MARKET_CAP_THRESHOLD
    ]
    logger.info(
        "大市值股票筛选完成: %s 只 (阈值 %.0f 亿)",
        len(ctx.big_cap_codes),
        MARKET_CAP_THRESHOLD / 1e8,
    )

    ctx.total_stocks = len(ctx.big_cap_codes)
    ctx.tasks = [(code, ctx.hist_start_date) for code in ctx.big_cap_codes]
    return ctx


def _iter_stock_history(ctx: StockImportContext):
    with ProcessPoolExecutor(
        max_workers=STOCK_HISTORY_FETCH_WORKERS,
        initializer=_baostock_worker_init,
    ) as executor:
        futures = {
            executor.submit(_fetch_stock_amount_worker, task): task[0]
            for task in ctx.tasks
        }
        for i, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            try:
                code, hist_fr = future.result()
            except Exception as e:
                msg = f"个股 {code} 处理异常: {e}"
                logger.warning(msg)
                ctx.stock_errors.append(msg)
                continue
            yield i, code, hist_fr


def _import_stock_gen(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
):
    ctx = _init_stock_context(db, on_progress=on_progress, bridge=bridge)
    if ctx.is_skipped:
        return ctx.build_skip_result()

    for i, code, hist_fr in _iter_stock_history(ctx):
        ctx.accumulate(code, hist_fr)
        ctx.maybe_flush()

        if i % 20 == 0:
            logger.info("个股日线进度: %s/%s", i, ctx.total_stocks)
            yield from ctx.emit_stock_progress(i)
        elif i % 100 == 0 and ctx.on_progress is not None:
            ctx.on_progress.ping()
            if ctx.bridge is not None:
                yield from ctx.bridge.drain()

    ctx.flush_buffer()
    return ctx.build_result()


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
