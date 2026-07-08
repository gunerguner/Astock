from fastapi import APIRouter, Query

from astock.config import POINT_INDEX_CONFIG, TURNOVER_THRESHOLD
from astock.core.deps import DbSession
from astock.core.exceptions import AppError
from astock.schemas.analysis import (
    BullMarketStatsResponse,
    MarketOverviewResponse,
    MultiIndexPointStatsResponse,
    PriceLevelsResponse,
    StockRankingResponse,
    TurnoverRankingResponse,
)
from astock.schemas.response import ApiResponse, success
from astock.services.analysis_service import (
    bull_market_multi_index_point_stats,
    bull_market_turnover_stats,
    stock_ranking,
    turnover_ranking,
)
from astock.services.global_asset_service import get_price_levels
from astock.services.market_overview_service import get_market_overview

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get(
    "/bull-markets/point",
    response_model=ApiResponse[MultiIndexPointStatsResponse],
)
def bull_market_point_stats_api(
    db: DbSession,
    threshold_000001: float = Query(
        default=float(POINT_INDEX_CONFIG["000001"]["default_threshold"]),  # type: ignore[arg-type]
        gt=0,
    ),
    threshold_000300: float = Query(
        default=float(POINT_INDEX_CONFIG["000300"]["default_threshold"]),  # type: ignore[arg-type]
        gt=0,
    ),
    threshold_399006: float = Query(
        default=float(POINT_INDEX_CONFIG["399006"]["default_threshold"]),  # type: ignore[arg-type]
        gt=0,
    ),
    threshold_000688: float = Query(
        default=float(POINT_INDEX_CONFIG["000688"]["default_threshold"]),  # type: ignore[arg-type]
        gt=0,
    ),
):
    thresholds = {
        "000001": threshold_000001,
        "000300": threshold_000300,
        "399006": threshold_399006,
        "000688": threshold_000688,
    }
    return success(bull_market_multi_index_point_stats(db, thresholds))


@router.get(
    "/bull-markets/turnover",
    response_model=ApiResponse[BullMarketStatsResponse],
)
def bull_market_turnover_stats_api(
    db: DbSession,
    threshold: float = Query(default=TURNOVER_THRESHOLD, gt=0),
):
    return success(bull_market_turnover_stats(db, threshold))


@router.get(
    "/turnover/ranking",
    response_model=ApiResponse[TurnoverRankingResponse],
)
def turnover_ranking_api(
    db: DbSession,
    top: int = Query(default=20, ge=1, le=100),
    bull_market: str | None = Query(default=None),
):
    try:
        return success(turnover_ranking(db, top=top, bull_market=bull_market))
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get(
    "/stock/ranking",
    response_model=ApiResponse[StockRankingResponse],
)
def stock_ranking_api(
    db: DbSession,
    top: int = Query(default=20, ge=1, le=100),
    bull_market: str | None = Query(default=None),
):
    try:
        return success(stock_ranking(db, top=top, bull_market=bull_market))
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get(
    "/asset-price-levels",
    response_model=ApiResponse[PriceLevelsResponse],
)
def asset_price_levels_api(
    db: DbSession,
    force_refresh: bool = Query(default=False),
):
    try:
        return success(get_price_levels(db, force_refresh=force_refresh))
    except ValueError as e:
        raise AppError(str(e)) from e


@router.get(
    "/market-overview",
    response_model=ApiResponse[MarketOverviewResponse],
)
def market_overview_api(
    force_refresh: bool = Query(default=False),
):
    return success(get_market_overview(force_refresh=force_refresh))
