"""牛市区间统计查询。"""

from sqlalchemy import func
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlmodel import Session, SQLModel, select

from astock.config import BULL_MARKETS, POINT_INDEX_CONFIG
from astock.core.exceptions import AppError
from astock.models.point import Point
from astock.models.turnover import Turnover
from astock.schemas.analysis import (
    BullMarketItem,
    BullMarketStatsResponse,
    IndexPointStats,
    MultiIndexPointStatsResponse,
)
from astock.services.queries._common import empty_index_items, require_rows


def build_bull_market_stats(
    db: Session,
    model: type[SQLModel],
    value_col: InstrumentedAttribute,
    threshold: float,
    *,
    extra_where: list | None = None,
    available_from: str | None = None,
) -> BullMarketStatsResponse:
    items: list[BullMarketItem] = []
    total_days = 0
    extra_where = extra_where or []

    for market_name, period in BULL_MARKETS.items():
        if available_from and available_from > period["end"]:
            items.append(
                BullMarketItem(
                    market=market_name,
                    start=period["start"],
                    end=period["end"],
                    description=period.get("description"),
                    days=0,
                    max_value=None,
                    not_available=True,
                )
            )
            continue

        where_clauses = [
            model.date >= period["start"],
            model.date <= period["end"],
            value_col > threshold,
            *extra_where,
        ]
        count, max_value = db.exec(
            select(func.count(), func.max(value_col)).where(*where_clauses)
        ).one()
        days = int(count or 0)
        total_days += days
        max_val = float(max_value) if max_value is not None else None
        if days > 0 and max_val is None:
            raise AppError(message=f"牛市区间 {market_name} 存在达标天数但缺少极值，请重新导入数据")
        items.append(
            BullMarketItem(
                market=market_name,
                start=period["start"],
                end=period["end"],
                description=period.get("description"),
                days=days,
                max_value=max_val,
            )
        )

    items.sort(key=lambda x: x.end, reverse=True)
    return BullMarketStatsResponse(
        threshold=threshold,
        items=items,
        total_days=total_days,
    )


def bull_market_multi_index_point_stats(
    db: Session, thresholds: dict[str, float]
) -> MultiIndexPointStatsResponse:
    indices: list[IndexPointStats] = []

    for index_code, config in POINT_INDEX_CONFIG.items():
        threshold = thresholds.get(
            index_code, float(config["default_threshold"])  # type: ignore[arg-type]
        )
        index_name = str(config["name"])
        available_from = str(config["available_from"])
        exists = db.exec(
            select(Point).where(Point.index_code == index_code).limit(1)
        ).first()
        if exists is None:
            items = empty_index_items(available_from)
            indices.append(
                IndexPointStats(
                    index_code=index_code,
                    index_name=index_name,
                    threshold=threshold,
                    items=items,
                    total_days=0,
                )
            )
            continue

        stats = build_bull_market_stats(
            db,
            Point,
            Point.close,
            threshold,
            extra_where=[Point.index_code == index_code],
            available_from=available_from,
        )
        indices.append(
            IndexPointStats(
                index_code=index_code,
                index_name=index_name,
                threshold=threshold,
                items=stats.items,
                total_days=stats.total_days,
            )
        )

    return MultiIndexPointStatsResponse(indices=indices)


def bull_market_turnover_stats(db: Session, threshold: float) -> BullMarketStatsResponse:
    require_rows(db, Turnover, "成交额数据为空，请先导入数据")
    return build_bull_market_stats(db, Turnover, Turnover.turnover, threshold)
