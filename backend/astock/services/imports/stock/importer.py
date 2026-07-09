"""个股切片导入编排入口。"""

import logging
from collections.abc import Iterator
from typing import Any

from sqlmodel import Session

from astock.config import START_DATE, STOCK_HISTORY_FETCH_WORKERS
from astock.core.datetime_utils import last_settled_date
from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports._common import build_skip_result
from astock.services.imports.stock.context import StockImportContext
from astock.services.imports.stock.history import iter_stock_history
from astock.services.imports.stock.path_select import build_candidate_pool, select_path
from astock.services.imports.stock.snapshot import drain_bridge, load_spot_snapshot, report_stock
from astock.services.imports.turnover import import_turnover
from astock.services.price_utils import iso_now
from astock.services.sync_store import count_rows, get_last_date, get_sync_meta
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _init_stock_context(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
) -> Iterator[str] | StockImportContext:
    ctx = StockImportContext(db=db, on_progress=on_progress, bridge=bridge)

    turnover_count = count_rows(db, Turnover)
    if turnover_count == 0:
        report_stock(on_progress, "成交额表为空，先导入成交额...")
        yield from drain_bridge(bridge)
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
    ctx.last_synced = last_synced
    ctx.hist_start_date = last_synced or START_DATE
    ctx.cached_at = iso_now()

    logger.info(
        "个股切片导入: as_of=%s, last_synced=%s, settled=%s, workers=%s",
        as_of_date,
        last_synced,
        last_settled_date("cn"),
        STOCK_HISTORY_FETCH_WORKERS,
    )

    spot_gen = load_spot_snapshot(ctx)
    spot_fr = None
    try:
        while True:
            yield next(spot_gen)
    except StopIteration as exc:
        spot_fr = exc.value

    assert isinstance(spot_fr, SourceFetchResult)
    build_candidate_pool(ctx, spot_fr.records)
    if not ctx.big_cap_codes:
        raise ExternalSourceAppError("大市值候选池为空，无法导入个股切片")

    select_path(ctx)
    ctx.total_stocks = len(ctx.tasks)

    if ctx.use_snapshot_for_as_of and not ctx.tasks:
        report_stock(
            on_progress,
            f"路径 A：快照直写 {as_of_date}",
            current=0,
            total=1,
        )
    else:
        report_stock(
            on_progress,
            f"开始拉取个股日线，共 {ctx.total_stocks} 只"
            + ("（含 as_of 快照）" if ctx.use_snapshot_for_as_of else ""),
            current=0,
            total=max(ctx.total_stocks, 1),
        )
    yield from drain_bridge(bridge)
    return ctx


def import_stock_gen(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
):
    init_gen = _init_stock_context(db, on_progress=on_progress, bridge=bridge)
    ctx = None
    try:
        while True:
            yield next(init_gen)
    except StopIteration as exc:
        ctx = exc.value

    if ctx.is_skipped:
        result = build_skip_result(
            db,
            table_name="stock_turnover",
            model=StockTurnover,
            source_key="stock",
            start_ts=ctx.start_ts,
            last_date=get_last_date(db, StockTurnover),
        )
        logger.info(
            "个股切片导入跳过: 无新交易日 (as_of=%s)",
            ctx.as_of_date,
        )
        return result

    if ctx.use_snapshot_for_as_of and ctx.as_of_date:
        added = ctx.append_snapshot_slice(ctx.as_of_date)
        logger.info("快照直写 as_of=%s: %s 条候选切片", ctx.as_of_date, added)
        ctx.maybe_flush()

    if ctx.tasks:
        for i, code, hist_fr in iter_stock_history(ctx):
            ctx.accumulate(code, hist_fr)
            ctx.maybe_flush()

            if i % 5 == 0:
                logger.info("个股日线进度: %s/%s", i, ctx.total_stocks)
                yield from ctx.emit_stock_progress(i)
            elif on_progress is not None:
                on_progress.ping()
                yield from drain_bridge(bridge)

    ctx.flush_buffer()
    return ctx.build_result()


def import_stock(
    db: Session,
    on_progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    gen = import_stock_gen(db, on_progress=on_progress)
    try:
        while True:
            next(gen)
    except StopIteration as exc:
        return exc.value
