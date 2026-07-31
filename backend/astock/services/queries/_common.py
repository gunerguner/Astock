"""分析查询公共工具。"""


from collections.abc import Callable, Sequence
from typing import Any

from fastapi import status
from sqlmodel import Session, SQLModel, col, select

from astock.config import BULL_MARKETS
from astock.core.error_codes import ErrorCode
from astock.core.exceptions import AppError
from astock.core.types import MacroMetric, MacroRegion
from astock.models.macro import MacroValue
from astock.schemas.analysis import BullMarketItem


def get_bull_market_period(bull_market: str | None) -> tuple[str, str] | None:
    if not bull_market or bull_market == "all":
        return None
    period = BULL_MARKETS.get(bull_market)
    if period is None:
        raise AppError(
            message=f"未知牛市区间: {bull_market}",
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return period["start"], period["end"]


def require_rows(db: Session, model: type[SQLModel], empty_message: str) -> None:
    exists = db.exec(select(model).limit(1)).first()
    if exists is None:
        raise AppError(message=empty_message)


def bull_market_item_skeleton(
    market_name: str,
    *,
    available_from: str | None = None,
    days: int = 0,
    max_value: float | None = None,
) -> BullMarketItem:
    """按牛市区间配置构造 BullMarketItem 骨架。"""
    period = BULL_MARKETS[market_name]
    not_available = bool(available_from and available_from > period["end"])
    return BullMarketItem(
        market=market_name,
        start=period["start"],
        end=period["end"],
        description=period.get("description") or "",
        days=days,
        max_value=max_value,
        not_available=not_available,
    )


def empty_index_items(available_from: str | None = None) -> list[BullMarketItem]:
    items = [
        bull_market_item_skeleton(name, available_from=available_from)
        for name in BULL_MARKETS
    ]
    items.sort(key=lambda x: x.end, reverse=True)
    return items


def pivot_macro_rows(
    rows: list[MacroValue],
    metrics: tuple[MacroMetric, ...],
) -> dict[str, dict[str, float | None]]:
    """将长表 MacroValue 行按 period 聚合为 metric → value 字典。"""
    by_period: dict[str, dict[str, float | None]] = {}
    empty = {m: None for m in metrics}
    for row in rows:
        bucket = by_period.setdefault(row.period, dict(empty))
        bucket[row.metric] = row.value
    return by_period


def load_macro_rows(
    db: Session,
    *,
    region: MacroRegion,
    metrics: tuple[MacroMetric, ...],
    start_period: str,
) -> list[MacroValue]:
    """按 region / 起始月 / 指标列表加载宏观长表行。"""
    return list(
        db.exec(
            select(MacroValue)
            .where(col(MacroValue.region) == region)
            .where(col(MacroValue.period) >= start_period)
            .where(col(MacroValue.metric).in_(metrics))
            .order_by(col(MacroValue.period), col(MacroValue.metric))
        ).all()
    )


def latest_period_with(
    points: Sequence[Any],
    *,
    predicate: Callable[[Any], bool],
) -> str | None:
    """从后往前找第一个满足 predicate 的 period；否则取末条 period。"""
    for point in reversed(points):
        if predicate(point):
            return point.period
    return points[-1].period if points else None
