from fastapi import APIRouter, Query, Request, status

from astock.config import (
    POINT_INDEX_CONFIG,
    TURNOVER_THRESHOLD,
    US_MACRO_START_PERIOD,
    cn_macro_start_period,
)
from astock.core.deps import DbSession
from astock.core.datetime_utils import is_valid_period
from astock.core.errors import AppError, ErrorCode
from astock.core.rate_limit import client_ip, force_refresh_limit
from astock.schemas.analysis import (
    BullMarketStatsResponse,
    CnMacroResponse,
    MarketOverviewResponse,
    MultiIndexPointStatsResponse,
    PriceLevelsResponse,
    StockRankingResponse,
    TurnoverRankingResponse,
    UsMacroResponse,
)
from astock.schemas.response import ApiResponse, success
from astock.services.queries import (
    bull_market_multi_index_point_stats,
    bull_market_turnover_stats,
    get_cn_macro,
    get_market_overview,
    get_price_levels,
    get_us_macro,
    stock_ranking,
    turnover_ranking,
)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


def _require_period(start: str) -> str:
    if not is_valid_period(start):
        raise AppError(
            message="start 须为 YYYY-MM",
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return start


def _index_thresholds(request: Request) -> dict[str, float]:
    """按已配置指数读取 threshold_{code}；缺省用 YAML，未知参数忽略。"""
    thresholds: dict[str, float] = {}
    for code, item in POINT_INDEX_CONFIG.items():
        raw = request.query_params.get(f"threshold_{code}")
        if raw is None or raw == "":
            thresholds[code] = float(item["default_threshold"])
            continue
        try:
            value = float(raw)
        except ValueError as exc:
            raise AppError(
                message=f"threshold_{code} 须为数字",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc
        if value <= 0:
            raise AppError(
                message=f"threshold_{code} 须大于 0",
                code=ErrorCode.VALIDATION_ERROR,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        thresholds[code] = value
    return thresholds


@router.get(
    "/bull-markets/point",
    response_model=ApiResponse[MultiIndexPointStatsResponse],
)
def bull_market_point_stats_api(db: DbSession, request: Request):
    return success(bull_market_multi_index_point_stats(db, _index_thresholds(request)))


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
    return success(turnover_ranking(db, top=top, bull_market=bull_market))


@router.get(
    "/stock/ranking",
    response_model=ApiResponse[StockRankingResponse],
)
def stock_ranking_api(
    db: DbSession,
    top: int = Query(default=20, ge=1, le=100),
    bull_market: str | None = Query(default=None),
):
    return success(stock_ranking(db, top=top, bull_market=bull_market))


@router.get(
    "/asset-price-levels",
    response_model=ApiResponse[PriceLevelsResponse],
)
def asset_price_levels_api(
    db: DbSession,
    request: Request,
    force_refresh: bool = Query(default=False),
):
    if force_refresh:
        force_refresh_limit.hit(_client_ip(request))
    return success(get_price_levels(db, force_refresh=force_refresh))


@router.get(
    "/market-overview",
    response_model=ApiResponse[MarketOverviewResponse],
)
def market_overview_api(
    request: Request,
    force_refresh: bool = Query(default=False),
):
    if force_refresh:
        force_refresh_limit.hit(client_ip(request))
    return success(get_market_overview(force_refresh=force_refresh))


@router.get(
    "/us-macro",
    response_model=ApiResponse[UsMacroResponse],
)
def us_macro_api(
    db: DbSession,
    start: str = Query(default=""),
):
    period = _require_period(start or US_MACRO_START_PERIOD)
    return success(get_us_macro(db, start=period))


@router.get(
    "/cn-macro",
    response_model=ApiResponse[CnMacroResponse],
)
def cn_macro_api(
    db: DbSession,
    start: str = Query(default=""),
):
    period = _require_period(start or cn_macro_start_period())
    return success(get_cn_macro(db, start=period))
