from fastapi import APIRouter

from astock.schemas.analysis import BullMarketsMetaResponse
from astock.schemas.response import ApiResponse, success
from astock.services.analysis_service import get_bull_markets_meta

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get(
    "/bull-markets",
    response_model=ApiResponse[BullMarketsMetaResponse],
)
def bull_markets_meta():
    return success(get_bull_markets_meta())
