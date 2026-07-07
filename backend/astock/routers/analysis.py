from fastapi import APIRouter, Query

from astock.config import THRESHOLD_POINT, TURNOVER_THRESHOLD
from astock.core.decorators import handle_success_response
from astock.core.deps import DbSession
from astock.core.exceptions import AppError
from astock.services.analysis_service import (
    build_bull_market_stats,
    get_point_dataframe,
    get_turnover_dataframe,
    stock_ranking,
    turnover_ranking,
)
from astock.services.global_asset_service import get_price_levels
from astock.services.market_overview_service import get_market_overview

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/bull-markets/point")
@handle_success_response
def bull_market_point_stats(
    db: DbSession,
    threshold: float = Query(default=THRESHOLD_POINT, gt=0),
):
    df = get_point_dataframe(db)
    if df.empty:
        raise AppError("上证点位数据为空，请先导入数据")
    return build_bull_market_stats(df, "close", threshold)


@router.get("/bull-markets/turnover")
@handle_success_response
def bull_market_turnover_stats(
    db: DbSession,
    threshold: float = Query(default=TURNOVER_THRESHOLD, gt=0),
):
    df = get_turnover_dataframe(db)
    if df.empty:
        raise AppError("成交额数据为空，请先导入数据")
    return build_bull_market_stats(df, "turnover", threshold)


@router.get("/turnover/ranking")
@handle_success_response
def turnover_ranking_api(
    db: DbSession,
    top: int = Query(default=20, ge=1, le=100),
    bull_market: str | None = Query(default=None),
):
    try:
        return turnover_ranking(db, top=top, bull_market=bull_market)
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get("/stock/ranking")
@handle_success_response
def stock_ranking_api(
    db: DbSession,
    top: int = Query(default=20, ge=1, le=100),
    bull_market: str | None = Query(default=None),
):
    try:
        return stock_ranking(db, top=top, bull_market=bull_market)
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get("/asset-price-levels")
@handle_success_response
def asset_price_levels_api(
    db: DbSession,
    force_refresh: bool = Query(default=False),
):
    try:
        return get_price_levels(db, force_refresh=force_refresh)
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get("/market-overview")
@handle_success_response
def market_overview_api(
    force_refresh: bool = Query(default=False),
):
    return get_market_overview(force_refresh=force_refresh)
