from fastapi import APIRouter

from astock.core.decorators import handle_success_response
from astock.services.analysis_service import get_bull_markets_meta

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/bull-markets")
@handle_success_response
def bull_markets_meta():
    return get_bull_markets_meta()
