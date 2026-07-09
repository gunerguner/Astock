"""个股导入 Path A/B 决策与候选池。"""

import logging

from sqlmodel import Session, select

from astock.config import (
    MARKET_CAP_THRESHOLD,
    PATH_B_CANDIDATE_AMOUNT_FLOOR,
    START_DATE,
)
from astock.core.datetime_utils import add_calendar_days, last_settled_date, today_local
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports.stock.context import StockImportContext

logger = logging.getLogger(__name__)


def historical_slice_codes(db: Session) -> set[str]:
    rows = db.exec(select(StockTurnover.code).distinct()).all()
    return {str(code) for code in rows if code}


def build_candidate_pool(ctx: StockImportContext, spot_records: list[dict]) -> None:
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


def narrow_path_b_codes(ctx: StockImportContext) -> list[str]:
    hist_codes = historical_slice_codes(ctx.db)
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


def has_turnover_between(db: Session, start_exclusive: str, end_exclusive: str) -> bool:
    """(start, end) 开区间内是否存在成交额交易日。"""
    row = db.exec(
        select(Turnover.date)
        .where(Turnover.date > start_exclusive)
        .where(Turnover.date < end_exclusive)
        .limit(1)
    ).first()
    return row is not None


def select_path(ctx: StockImportContext) -> None:
    """决定是否快照直写 as_of，以及 baostock 区间。"""
    as_of = ctx.as_of_date
    assert as_of is not None
    settled = last_settled_date("cn")
    last_synced = ctx.last_synced
    missing_start = add_calendar_days(last_synced, 1) if last_synced else START_DATE

    can_snapshot_as_of = as_of == settled == today_local()
    gap_only_as_of = bool(last_synced) and not has_turnover_between(
        ctx.db, last_synced, as_of
    )

    ctx.use_snapshot_for_as_of = can_snapshot_as_of
    if can_snapshot_as_of and gap_only_as_of:
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
        ctx.use_snapshot_for_as_of = False
        ctx.hist_start_date = missing_start
        ctx.hist_end_date = as_of

    ctx.path_b_codes = narrow_path_b_codes(ctx)
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
