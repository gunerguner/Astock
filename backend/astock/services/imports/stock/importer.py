"""个股切片导入：baostock 按日全市场 TopN。"""

import logging
import time
from collections.abc import Iterator
from typing import Any

from sqlmodel import Session, select

from astock.config import START_DATE, STOCK_SLICE_TOP_N, STOCK_UPSERT_FLUSH_SIZE
from astock.core.datetime_utils import iso_now
from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.core.sync_status import SyncStatus
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports._common import (
    build_result,
    build_skip_result,
    finalize_import_result,
    is_missing_value,
    resolve_status,
)
from astock.services.imports.turnover import import_turnover
from astock.services.sync_store import (
    batch_upsert,
    count_rows,
    get_last_date,
    get_sync_meta,
    upsert_sync_meta,
)
from astock.sources.baostock import (
    baostock_session,
    fetch_all_stock_codes_logged_in,
    fetch_daily_astock_amounts_logged_in,
)
from astock.sources.baostock.session import login_failure

logger = logging.getLogger(__name__)


def _drain_bridge(bridge: SSEBridge | None) -> Iterator[str]:
    if bridge is not None:
        yield from bridge.drain()


def _report(
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


def _gap_trading_days(
    db: Session, *, last_synced: str | None, as_of: str
) -> list[str]:
    """turnover 表中 (last_synced, as_of] 的交易日；首次从 START_DATE 起。"""
    query = select(Turnover.date).where(Turnover.date <= as_of)
    if last_synced:
        query = query.where(Turnover.date > last_synced)
    else:
        query = query.where(Turnover.date >= START_DATE)
    rows = db.exec(query.order_by(Turnover.date)).all()
    return [str(d) for d in rows if d]


def _names_from_fetch(fr) -> dict[str, str]:
    if not fr.ok:
        logger.warning("代码名称清单失败: %s", fr.error_summary())
        return {}
    return {
        str(r["code"]): str(r.get("name") or "")
        for r in fr.records
        if r.get("code")
    }


def _top_n_records(
    amounts: list[dict[str, Any]],
    *,
    trade_date: str,
    names: dict[str, str],
    cached_at: str,
    top_n: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    ranked = sorted(
        amounts,
        key=lambda r: float(r.get("amount") or 0),
        reverse=True,
    )[:top_n]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in ranked:
        code = str(row["code"])
        amount = float(row["amount"])
        name = names.get(code, "")
        if is_missing_value(name):
            errors.append(f"个股 {code}@{trade_date}: 缺少股票名称")
            continue
        records.append(
            {
                "date": trade_date,
                "code": code,
                "name": name,
                "amount": amount,
                "cached_at": cached_at,
            }
        )
    return records, errors


def import_stock_gen(
    db: Session,
    *,
    on_progress: ProgressReporter | None = None,
    bridge: SSEBridge | None = None,
):
    start_ts = time.perf_counter()
    errors: list[str] = []
    imported = 0
    record_buffer: list[dict[str, Any]] = []

    turnover_count = count_rows(db, Turnover)
    if turnover_count == 0:
        _report(on_progress, "成交额表为空，先导入成交额...")
        yield from _drain_bridge(bridge)
        import_turnover(db)

    meta = get_sync_meta(db, "stock_turnover")
    last_synced = meta.last_synced_date if meta else None
    as_of_date = get_last_date(db, Turnover)
    if as_of_date is None:
        raise ExternalSourceAppError("无法确定有效交易日：turnover 表为空")

    if last_synced and as_of_date <= last_synced:
        result = build_skip_result(
            db,
            table_name="stock_turnover",
            model=StockTurnover,
            source_key="stock",
            start_ts=start_ts,
            last_date=get_last_date(db, StockTurnover),
        )
        logger.info("个股切片导入跳过: 无新交易日 (as_of=%s)", as_of_date)
        return result

    gap_days = _gap_trading_days(db, last_synced=last_synced, as_of=as_of_date)
    if not gap_days:
        result = build_skip_result(
            db,
            table_name="stock_turnover",
            model=StockTurnover,
            source_key="stock",
            start_ts=start_ts,
            last_date=get_last_date(db, StockTurnover),
        )
        logger.info(
            "个股切片导入跳过: turnover 无缺口日 (last_synced=%s as_of=%s)",
            last_synced,
            as_of_date,
        )
        return result

    cached_at = iso_now()
    total_days = len(gap_days)
    logger.info(
        "个股切片导入: as_of=%s last_synced=%s days=%s top_n=%s",
        as_of_date,
        last_synced,
        total_days,
        STOCK_SLICE_TOP_N,
    )
    _report(
        on_progress,
        f"按日全市场 Top{STOCK_SLICE_TOP_N}，共 {total_days} 日",
        current=0,
        total=total_days,
    )
    yield from _drain_bridge(bridge)

    with baostock_session() as lg:
        if failed := login_failure(lg):
            raise ExternalSourceAppError(failed.errors[0])

        # 名称按锚点日拉一次，缺口期内复用
        _report(
            on_progress,
            f"拉取名称清单 ({as_of_date})",
            current=0,
            total=total_days,
        )
        yield from _drain_bridge(bridge)
        names = _names_from_fetch(fetch_all_stock_codes_logged_in(as_of_date))
        if not names:
            raise ExternalSourceAppError(
                f"个股切片导入失败: 名称清单为空 (as_of={as_of_date})"
            )

        for i, trade_date in enumerate(gap_days, start=1):
            _report(
                on_progress,
                f"拉取 {trade_date} ({i}/{total_days})",
                current=i,
                total=total_days,
                imported=imported,
            )
            yield from _drain_bridge(bridge)

            amounts_fr = fetch_daily_astock_amounts_logged_in(trade_date)
            if not amounts_fr.ok or not amounts_fr.records:
                msg = amounts_fr.error_summary() or f"{trade_date}: 全市场日K为空"
                errors.append(msg)
                logger.warning("个股切片日失败: %s", msg)
                continue

            day_records, name_errors = _top_n_records(
                amounts_fr.records,
                trade_date=trade_date,
                names=names,
                cached_at=cached_at,
                top_n=STOCK_SLICE_TOP_N,
            )
            for msg in name_errors:
                logger.warning("%s", msg)
            if not day_records:
                errors.append(f"{trade_date}: Top{STOCK_SLICE_TOP_N} 无有效名称记录")
                continue
            record_buffer.extend(day_records)

            if len(record_buffer) >= STOCK_UPSERT_FLUSH_SIZE:
                imported += batch_upsert(
                    db,
                    StockTurnover,
                    record_buffer,
                    ["date", "code"],
                    commit_mode="single",
                )
                record_buffer = []

            if on_progress is not None:
                on_progress.ping()
            yield from _drain_bridge(bridge)

    if record_buffer:
        imported += batch_upsert(
            db,
            StockTurnover,
            record_buffer,
            ["date", "code"],
            commit_mode="single",
        )

    # 全部成功才推进水位；失败保留旧水位，下次重跑缺口（upsert 幂等）
    ok = len(errors) == 0
    status = resolve_status(ok, imported)
    synced_date = as_of_date if ok else last_synced
    last_synced_at = upsert_sync_meta(
        db,
        "stock_turnover",
        last_synced_date=synced_date,
        status=status,
        error="; ".join(errors[:5]) if errors else None,
    )

    result = build_result(
        imported=imported,
        total=count_rows(db, StockTurnover),
        last_date=synced_date or get_last_date(db, StockTurnover),
        ok=ok,
        source_errors={"stock": "; ".join(errors[:5]) if errors else None},
        last_synced_at=last_synced_at,
    )
    if result["status"] == SyncStatus.FAILED:
        raise ExternalSourceAppError(
            f"个股切片导入失败: {result['source_errors'].get('stock')}"
        )
    return finalize_import_result(
        result, start_ts=start_ts, log_label="个股切片导入"
    )

