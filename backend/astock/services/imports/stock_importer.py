"""个股切片数据导入。"""

import logging
import time
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import baostock as bs
from sqlmodel import Session, select

from astock.config import (
    MARKET_CAP_THRESHOLD,
    PATH_B_CANDIDATE_AMOUNT_FLOOR,
    START_DATE,
    STOCK_HISTORY_FETCH_WORKERS,
    STOCK_TURNOVER_SLICE_THRESHOLD,
    STOCK_UPSERT_FLUSH_SIZE,
)
from astock.core.datetime_utils import add_calendar_days, last_settled_date, today_local
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
from astock.sources.akshare_client import fetch_stock_spot_snapshot
from astock.sources.baostock import (
    configure_worker_socket,
    fetch_all_stock_codes,
    fetch_stock_amount_history,
)
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.tencent_client import TencentQuoteClient

logger = logging.getLogger(__name__)

tencent_client = TencentQuoteClient()


def _drain_bridge(bridge: SSEBridge | None) -> Iterator[str]:
    if bridge is not None:
        yield from bridge.drain()


def _report_stock(
    on_progress: ProgressReporter | None,
    detail: str,
    *,
    current: int = 0,
    total: int = 1,
    imported: int = 0,
) -> None:
    if on_progress is not None:
        on_progress.phase_progress(
            "stock", current, total, detail, imported=imported
        )


def _baostock_worker_init() -> None:
    """ProcessPool worker 初始化：每个子进程登录一次 baostock 会话。"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock worker 登录失败: {lg.error_msg}")
    configure_worker_socket()


def _fetch_stock_amount_worker(
    task: tuple[str, str | None, str | None],
) -> tuple[str, SourceFetchResult]:
    """在子进程中抓取单只股票历史成交额。"""
    code, start_date, end_date = task
    try:
        fr = fetch_stock_amount_history(code, start_date=start_date, end_date=end_date)
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
    snapshot_by_code: dict[str, dict[str, Any]] = field(default_factory=dict)
    big_cap_codes: list[str] = field(default_factory=list)
    path_b_codes: list[str] = field(default_factory=list)
    total_stocks: int = 0
    tasks: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    as_of_date: str | None = None
    last_synced: str | None = None
    hist_start_date: str = START_DATE
    hist_end_date: str | None = None
    use_snapshot_for_as_of: bool = False
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

    def append_snapshot_slice(self, date: str) -> int:
        """从快照直写 as_of 日切片，返回写入缓冲条数。"""
        added = 0
        for code in self.big_cap_codes:
            spot = self.snapshot_by_code.get(code)
            if not spot:
                continue
            amount = spot.get("amount")
            if is_missing_value(amount) or amount < STOCK_TURNOVER_SLICE_THRESHOLD:
                continue
            name = self.code_to_name.get(code) or spot.get("name") or ""
            if is_missing_value(name):
                self.stock_errors.append(f"个股 {code}: 缺少股票名称")
                continue
            self.record_buffer.append(
                {
                    "date": date,
                    "code": code,
                    "name": name,
                    "amount": float(amount),
                    "cached_at": self.cached_at,
                }
            )
            added += 1
        return added

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


def _load_spot_snapshot(
    ctx: StockImportContext,
) -> Iterator[str] | SourceFetchResult:
    """主路径 akshare 一次快照；失败则 baostock 代码池 + 腾讯批量回退。"""
    _report_stock(ctx.on_progress, "获取全市场个股快照...")
    yield from _drain_bridge(ctx.bridge)

    spot_fr = fetch_stock_spot_snapshot()
    if spot_fr.ok and spot_fr.records:
        return spot_fr

    if not spot_fr.ok:
        # 主源失败仅记日志；回退成功则不向用户暴露中间态
        logger.warning("akshare 快照失败，回退腾讯: %s", spot_fr.error_summary())

    _report_stock(ctx.on_progress, "akshare 失败，回退腾讯行情...")
    yield from _drain_bridge(ctx.bridge)

    codes_fr = fetch_all_stock_codes(ctx.as_of_date or "")
    if not codes_fr.ok or not codes_fr.records:
        raise ExternalSourceAppError(
            f"全市场代码清单获取失败: {codes_fr.error_summary()}"
        )

    code_list = [r["code"] for r in codes_fr.records]
    name_by_code = {r["code"]: r["name"] for r in codes_fr.records}

    records: list[dict] = []
    cap_errors: list[str] = []
    for batch_idx, total_batches, batch_records, error in tencent_client.iter_spot_batches(
        code_list
    ):
        _report_stock(
            ctx.on_progress,
            f"腾讯快照 {batch_idx}/{total_batches}",
            current=batch_idx,
            total=total_batches,
        )
        yield from _drain_bridge(ctx.bridge)
        if error:
            cap_errors.append(error)
            continue
        for row in batch_records:
            code = row["code"]
            if not row.get("name"):
                row["name"] = name_by_code.get(code, "")
            records.append(row)

    if not records:
        # 回退也失败：把主源 + 腾讯错误一并抛给用户
        detail = "; ".join((spot_fr.errors + cap_errors)[:3]) or "无有效记录"
        raise ExternalSourceAppError(f"股票快照失败(akshare+腾讯): {detail}")
    if cap_errors:
        # 有部分批次失败但仍拿到足够快照：记 warning，不污染最终成功态
        logger.warning(
            "腾讯快照部分批次失败(%s)，已用 %s 条继续: %s",
            len(cap_errors),
            len(records),
            "; ".join(cap_errors[:3]),
        )

    return SourceFetchResult(records=records, ok=True)


def _historical_slice_codes(db: Session) -> set[str]:
    rows = db.exec(select(StockTurnover.code).distinct()).all()
    return {str(code) for code in rows if code}


def _build_candidate_pool(ctx: StockImportContext, spot_records: list[dict]) -> None:
    ctx.snapshot_by_code = {r["code"]: r for r in spot_records}
    ctx.code_to_name = {
        r["code"]: r.get("name") or ""
        for r in spot_records
        if r.get("name")
    }
    ctx.big_cap_codes = [
        r["code"]
        for r in spot_records
        if r.get("market_cap", 0) >= MARKET_CAP_THRESHOLD
    ]
    logger.info(
        "大市值候选池: %s 只 (阈值 %.0f 亿)",
        len(ctx.big_cap_codes),
        MARKET_CAP_THRESHOLD / 1e8,
    )


def _narrow_path_b_codes(ctx: StockImportContext) -> list[str]:
    hist_codes = _historical_slice_codes(ctx.db)
    narrowed: list[str] = []
    for code in ctx.big_cap_codes:
        spot = ctx.snapshot_by_code.get(code) or {}
        amount = float(spot.get("amount") or 0)
        if amount >= PATH_B_CANDIDATE_AMOUNT_FLOOR or code in hist_codes:
            narrowed.append(code)
    logger.info(
        "Path B 候选池收窄: %s → %s (floor=%.0f 亿 ∪ 历史切片)",
        len(ctx.big_cap_codes),
        len(narrowed),
        PATH_B_CANDIDATE_AMOUNT_FLOOR / 1e8,
    )
    return narrowed


def _has_turnover_between(db: Session, start_exclusive: str, end_exclusive: str) -> bool:
    """(start, end) 开区间内是否存在成交额交易日。"""
    row = db.exec(
        select(Turnover.date)
        .where(Turnover.date > start_exclusive)
        .where(Turnover.date < end_exclusive)
        .limit(1)
    ).first()
    return row is not None


def _select_path(ctx: StockImportContext) -> None:
    """决定是否快照直写 as_of，以及 baostock 区间。"""
    as_of = ctx.as_of_date
    assert as_of is not None
    settled = last_settled_date("cn")
    last_synced = ctx.last_synced
    missing_start = add_calendar_days(last_synced, 1) if last_synced else START_DATE

    # 仅当 as_of 为「今日已结算」时可用实时快照直写，避免盘中用当日累计额填昨日
    can_snapshot_as_of = as_of == settled == today_local()
    # 日常单日：as_of 已结算，且 last_synced 与 as_of 之间无其它成交额交易日（含周末跳空）
    gap_only_as_of = bool(last_synced) and not _has_turnover_between(
        ctx.db, last_synced, as_of
    )

    ctx.use_snapshot_for_as_of = can_snapshot_as_of
    if can_snapshot_as_of and gap_only_as_of:
        # 路径 A：仅快照，0 baostock
        ctx.path_b_codes = []
        ctx.tasks = []
        ctx.hist_end_date = None
        logger.info(
            "个股切片路径 A: 快照直写 as_of=%s (settled=%s, last_synced=%s)",
            as_of,
            settled,
            last_synced,
        )
        return

    # 路径 B：中间日 baostock；as_of 若可结算则快照直写
    if can_snapshot_as_of:
        ctx.hist_end_date = add_calendar_days(as_of, -1)
        ctx.hist_start_date = missing_start
        if ctx.hist_start_date > ctx.hist_end_date:
            ctx.path_b_codes = []
            ctx.tasks = []
            logger.info(
                "个股切片路径 B(仅快照 as_of): as_of=%s hist 区间空", as_of
            )
            return
    else:
        # 盘中等：as_of 未结算，不能用快照填 as_of，整段走 baostock
        ctx.use_snapshot_for_as_of = False
        ctx.hist_start_date = missing_start
        ctx.hist_end_date = as_of

    ctx.path_b_codes = _narrow_path_b_codes(ctx)
    ctx.tasks = [
        (code, ctx.hist_start_date, ctx.hist_end_date) for code in ctx.path_b_codes
    ]
    logger.info(
        "个股切片路径 B: snapshot_as_of=%s hist=%s→%s baostock=%s",
        ctx.use_snapshot_for_as_of,
        ctx.hist_start_date,
        ctx.hist_end_date,
        len(ctx.tasks),
    )


def _init_stock_context(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
) -> Iterator[str] | StockImportContext:
    """初始化导入上下文；长耗时步骤前 yield SSE 保活帧。"""
    ctx = StockImportContext(db=db, on_progress=on_progress, bridge=bridge)

    turnover_count = count_rows(db, Turnover)
    if turnover_count == 0:
        _report_stock(on_progress, "成交额表为空，先导入成交额...")
        yield from _drain_bridge(bridge)
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

    spot_gen = _load_spot_snapshot(ctx)
    spot_fr = None
    try:
        while True:
            yield next(spot_gen)
    except StopIteration as exc:
        spot_fr = exc.value

    assert isinstance(spot_fr, SourceFetchResult)
    _build_candidate_pool(ctx, spot_fr.records)
    if not ctx.big_cap_codes:
        raise ExternalSourceAppError("大市值候选池为空，无法导入个股切片")

    _select_path(ctx)
    ctx.total_stocks = len(ctx.tasks)

    if ctx.use_snapshot_for_as_of and not ctx.tasks:
        _report_stock(
            on_progress,
            f"路径 A：快照直写 {as_of_date}",
            current=0,
            total=1,
        )
    else:
        _report_stock(
            on_progress,
            f"开始拉取个股日线，共 {ctx.total_stocks} 只"
            + ("（含 as_of 快照）" if ctx.use_snapshot_for_as_of else ""),
            current=0,
            total=max(ctx.total_stocks, 1),
        )
    yield from _drain_bridge(bridge)
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
    init_gen = _init_stock_context(db, on_progress=on_progress, bridge=bridge)
    ctx = None
    try:
        while True:
            yield next(init_gen)
    except StopIteration as exc:
        ctx = exc.value

    if ctx.is_skipped:
        return ctx.build_skip_result()

    if ctx.use_snapshot_for_as_of and ctx.as_of_date:
        added = ctx.append_snapshot_slice(ctx.as_of_date)
        logger.info("快照直写 as_of=%s: %s 条候选切片", ctx.as_of_date, added)
        ctx.maybe_flush()

    if ctx.tasks:
        for i, code, hist_fr in _iter_stock_history(ctx):
            ctx.accumulate(code, hist_fr)
            ctx.maybe_flush()

            if i % 5 == 0:
                logger.info("个股日线进度: %s/%s", i, ctx.total_stocks)
                yield from ctx.emit_stock_progress(i)
            elif on_progress is not None:
                on_progress.ping()
                yield from _drain_bridge(bridge)

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
