"""个股切片导入：baostock 按日全市场 TopN。"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from astock.config import START_DATE, STOCK_SLICE_TOP_N, STOCK_UPSERT_FLUSH_SIZE
from astock.core.datetime_utils import iso_now
from astock.core.errors import ExternalSourceAppError
from astock.core.sync_status import SyncStatus
from astock.datasets.stocks import (
    baostock_session,
    fetch_all_stock_codes_logged_in,
    fetch_daily_astock_amounts_logged_in,
    login_error,
)
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports._common import build_skip_result
from astock.services.imports.progress import ProgressReporter, SSEBridge
from astock.services.imports.stock_names import names_from_fetch, resolve_name
from astock.services.imports.turnover import import_turnover
from astock.services.sync.results import ImportResult, build_result, finalize_import_result
from astock.services.sync.store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.services.sync.watermark import forward_date

logger = logging.getLogger(__name__)


@dataclass
class _DayFetchState:
    as_of_date: str
    last_synced: str | None
    gap_days: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    record_buffer: list[dict[str, Any]] = field(default_factory=list)
    imported: int = 0
    last_success: str | None = None
    failed_day: str | None = None


def _drain_bridge(bridge: SSEBridge) -> Iterator[str]:
    yield from bridge.drain()


def _report(
    on_progress: ProgressReporter,
    detail: str,
    *,
    current: int = 0,
    total: int = 1,
    imported: int = 0,
) -> None:
    on_progress.phase_progress("stock", current, total, detail, imported=imported)


def _gap_trading_days(db: Session, *, last_synced: str | None, as_of: str) -> list[str]:
    """turnover 表中 (last_synced, as_of] 的交易日；首次从 START_DATE 起。"""
    query = select(Turnover.date).where(Turnover.date <= as_of)
    if last_synced:
        query = query.where(Turnover.date > last_synced)
    else:
        query = query.where(Turnover.date >= START_DATE)
    rows = db.exec(query.order_by(Turnover.date)).all()
    return [str(d) for d in rows if d]


def _top_n_records(
    amounts: list[dict[str, Any]],
    *,
    trade_date: str,
    names: dict[str, str],
    day_names: dict[str, dict[str, str]],
    cached_at: str,
    top_n: int,
) -> list[dict[str, Any]]:
    ranked = sorted(amounts, key=lambda r: float(r.get("amount") or 0), reverse=True)[:top_n]
    return [
        {
            "date": trade_date,
            "code": str(row["code"]),
            "name": resolve_name(str(row["code"]), trade_date, names, day_names),
            "amount": float(row["amount"]),
            "cached_at": cached_at,
        }
        for row in ranked
    ]


def _skip_result(db: Session, start_ts: float) -> ImportResult:
    return build_skip_result(
        db,
        table_name="stock_turnover",
        model=StockTurnover,
        start_ts=start_ts,
        last_date=get_last_date(db, StockTurnover),
    )


def _skip_result_if_current(
    db: Session,
    *,
    last_synced: str | None,
    as_of_date: str,
    start_ts: float,
) -> tuple[list[str], ImportResult | None]:
    if last_synced and as_of_date <= last_synced:
        logger.info("个股切片导入跳过: 无新交易日 (as_of=%s)", as_of_date)
        return [], _skip_result(db, start_ts)
    gap_days = _gap_trading_days(db, last_synced=last_synced, as_of=as_of_date)
    if not gap_days:
        logger.info(
            "个股切片导入跳过: turnover 无缺口日 (last_synced=%s as_of=%s)",
            last_synced,
            as_of_date,
        )
        return [], _skip_result(db, start_ts)
    return gap_days, None


def _flush_buffer(db: Session, state: _DayFetchState) -> None:
    if not state.record_buffer:
        return
    state.imported += batch_upsert(db, StockTurnover, state.record_buffer, ["date", "code"])
    state.record_buffer = []


def _fetch_one_day(
    state: _DayFetchState,
    trade_date: str,
    *,
    names: dict[str, str],
    day_names: dict[str, dict[str, str]],
    cached_at: str,
) -> bool:
    """拉取单日 TopN。失败时写入 state 并返回 False。"""
    amounts_fr = fetch_daily_astock_amounts_logged_in(trade_date)
    if not amounts_fr.ok or not amounts_fr.records:
        msg = amounts_fr.error_summary() or f"{trade_date}: 全市场日K为空"
        state.errors.append(msg)
        logger.warning("个股切片日失败: %s", msg)
        state.failed_day = trade_date
        return False

    day_records = _top_n_records(
        amounts_fr.records,
        trade_date=trade_date,
        names=names,
        day_names=day_names,
        cached_at=cached_at,
        top_n=STOCK_SLICE_TOP_N,
    )
    if not day_records:
        state.errors.append(f"{trade_date}: 没有成交额行")
        state.failed_day = trade_date
        return False
    state.record_buffer.extend(day_records)
    state.last_success = trade_date
    return True


def _fetch_days_into_buffer(
    db: Session,
    state: _DayFetchState,
    on_progress: ProgressReporter,
    bridge: SSEBridge,
) -> Iterator[str]:
    total_days = len(state.gap_days)
    cached_at = iso_now()
    logger.info(
        "个股切片导入: as_of=%s last_synced=%s days=%s top_n=%s",
        state.as_of_date,
        state.last_synced,
        total_days,
        STOCK_SLICE_TOP_N,
    )
    _report(on_progress, f"按日全市场 Top{STOCK_SLICE_TOP_N}，共 {total_days} 日", total=total_days)
    yield from _drain_bridge(bridge)

    with baostock_session() as lg:
        if err := login_error(lg):
            raise ExternalSourceAppError(message=err)

        # 名称按锚点日拉一次，缺口期内复用
        _report(on_progress, f"拉取名称清单 ({state.as_of_date})", total=total_days)
        yield from _drain_bridge(bridge)
        names = names_from_fetch(fetch_all_stock_codes_logged_in(state.as_of_date))
        if not names:
            raise ExternalSourceAppError(
                message=f"个股切片导入失败: 名称清单为空 (as_of={state.as_of_date})"
            )
        day_names: dict[str, dict[str, str]] = {}

        for i, trade_date in enumerate(state.gap_days, start=1):
            _report(
                on_progress,
                f"拉取 {trade_date} ({i}/{total_days})",
                current=i,
                total=total_days,
                imported=state.imported,
            )
            yield from _drain_bridge(bridge)
            if not _fetch_one_day(
                state, trade_date, names=names, day_names=day_names, cached_at=cached_at
            ):
                break
            if len(state.record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
                _flush_buffer(db, state)
            on_progress.ping()
            yield from _drain_bridge(bridge)

    _flush_buffer(db, state)


def _finalize_watermark(db: Session, state: _DayFetchState, start_ts: float) -> ImportResult:
    # 水位停在第一个真正失败日的前一日；成功前缀下次不再重拉
    advanced = state.last_success is not None and state.last_success != state.last_synced
    ok = state.failed_day is None
    if ok:
        status = SyncStatus.SUCCESS
        synced_date = forward_date(
            forward_date(state.last_synced, state.last_success), state.as_of_date
        )
    elif advanced or state.imported > 0:
        status = SyncStatus.PARTIAL_FAILURE
        synced_date = forward_date(state.last_synced, state.last_success)
    else:
        status = SyncStatus.FAILED
        synced_date = state.last_synced
    error = "; ".join(state.errors[:5]) if state.errors else None
    last_synced_at = upsert_sync_meta(
        db,
        "stock_turnover",
        last_synced_date=synced_date,
        status=status,
        error=error,
    )
    result = build_result(
        imported=state.imported,
        total=count_rows(db, StockTurnover),
        last_date=synced_date or get_last_date(db, StockTurnover),
        ok=ok,
        status=status,
        source_errors={"stock": error} if error else {},
        last_synced_at=last_synced_at,
    )
    if result.status == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            message=f"个股切片导入失败: {result.source_errors.get('stock')}"
        )
    return finalize_import_result(result, start_ts=start_ts, log_label="个股切片导入")


def import_stock_gen(
    db: Session,
    *,
    on_progress: ProgressReporter,
    bridge: SSEBridge,
):
    start_ts = time.perf_counter()
    if count_rows(db, Turnover) == 0:
        _report(on_progress, "成交额表为空，先导入成交额...")
        yield from _drain_bridge(bridge)
        import_turnover(db)

    meta = get_sync_meta(db, "stock_turnover")
    last_synced = meta.last_synced_date if meta else None
    as_of_date = get_last_date(db, Turnover)
    if as_of_date is None:
        raise ExternalSourceAppError(message="无法确定有效交易日：turnover 表为空")

    gap_days, skipped = _skip_result_if_current(
        db, last_synced=last_synced, as_of_date=as_of_date, start_ts=start_ts
    )
    if skipped is not None:
        return skipped

    state = _DayFetchState(
        as_of_date=as_of_date,
        last_synced=last_synced,
        gap_days=gap_days,
        last_success=last_synced,
    )
    yield from _fetch_days_into_buffer(db, state, on_progress, bridge)
    return _finalize_watermark(db, state, start_ts)
