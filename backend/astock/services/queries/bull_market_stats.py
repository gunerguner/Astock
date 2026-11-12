"""牛市区间统计查询。"""

from typing import Any

from sqlalchemy import and_, case, func
from sqlmodel import Session, col, select

from astock.config import BULL_MARKETS, POINT_INDEX_CONFIG
from astock.models.point import Point
from astock.models.turnover import Turnover
from astock.schemas.analysis import (
    BullMarketItem,
    BullMarketStatsResponse,
    IndexPointStats,
    MultiIndexPointStatsResponse,
)
from astock.services.queries._common import (
    bull_market_item_skeleton,
    empty_index_items,
    require_rows,
)


def build_bull_market_stats(
    db: Session,
    model: type[Point] | type[Turnover],
    value_col: Any,
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
                bull_market_item_skeleton(market_name, available_from=available_from)
            )
            continue

        # 达标天数仍严格大于阈值；极值取整个牛市区间，低于阈值也保留。
        qualified = case((value_col > threshold, 1))
        count, max_value = db.exec(
            select(func.count(qualified), func.max(value_col)).where(
                col(model.date) >= period["start"],
                col(model.date) <= period["end"],
                *extra_where,
            )
        ).one()
        days = int(count or 0)
        total_days += days
        max_val = float(max_value) if max_value is not None else None
        items.append(
            bull_market_item_skeleton(
                market_name,
                available_from=available_from,
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


def _period_aggregate_columns(
    threshold: float, available_from: str | None
) -> tuple[list, list[str]]:
    """每个可统计区间一对达标天数 / 区间极值列，外加全指数行数。"""
    columns: list = [func.count().label("row_count")]
    queried: list[str] = []
    for market_name, period in BULL_MARKETS.items():
        if available_from and available_from > period["end"]:
            continue
        in_period = and_(
            col(Point.date) >= period["start"],
            col(Point.date) <= period["end"],
        )
        slug = market_name.replace("-", "_")
        columns.append(
            func.count(
                case((and_(in_period, col(Point.close) > threshold), 1))
            ).label(f"days_{slug}")
        )
        columns.append(
            func.max(case((in_period, col(Point.close)))).label(f"max_{slug}")
        )
        queried.append(market_name)
    return columns, queried


def bull_market_multi_index_point_stats(
    db: Session, thresholds: dict[str, float]
) -> MultiIndexPointStatsResponse:
    indices: list[IndexPointStats] = []

    for index_code, config in POINT_INDEX_CONFIG.items():
        raw_threshold = thresholds.get(index_code)
        threshold = (
            float(config["default_threshold"])
            if raw_threshold is None
            else float(raw_threshold)
        )
        index_name = config["name"]
        available_from = config["available_from"]
        columns, queried = _period_aggregate_columns(threshold, available_from)
        row = db.exec(
            select(*columns).where(Point.index_code == index_code)
        ).one()
        values = row._mapping
        if int(values["row_count"] or 0) == 0:
            indices.append(
                IndexPointStats(
                    index_code=index_code,
                    index_name=index_name,
                    threshold=threshold,
                    items=empty_index_items(available_from),
                    total_days=0,
                )
            )
            continue

        items: list[BullMarketItem] = []
        total_days = 0
        for market_name in BULL_MARKETS:
            if market_name not in queried:
                items.append(
                    bull_market_item_skeleton(
                        market_name, available_from=available_from
                    )
                )
                continue
            slug = market_name.replace("-", "_")
            days = int(values[f"days_{slug}"] or 0)
            max_raw = values[f"max_{slug}"]
            max_val = float(max_raw) if max_raw is not None else None
            total_days += days
            items.append(
                bull_market_item_skeleton(
                    market_name,
                    available_from=available_from,
                    days=days,
                    max_value=max_val,
                )
            )

        items.sort(key=lambda x: x.end, reverse=True)
        indices.append(
            IndexPointStats(
                index_code=index_code,
                index_name=index_name,
                threshold=threshold,
                items=items,
                total_days=total_days,
            )
        )

    return MultiIndexPointStatsResponse(indices=indices)


def bull_market_turnover_stats(db: Session, threshold: float) -> BullMarketStatsResponse:
    require_rows(db, Turnover, "成交额数据为空，请先导入数据")
    return build_bull_market_stats(db, Turnover, col(Turnover.turnover), threshold)
