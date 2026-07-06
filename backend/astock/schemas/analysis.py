from pydantic import BaseModel, Field


class BullMarketItem(BaseModel):
    market: str
    start: str
    end: str
    description: str | None = None
    days: int
    max_value: float | None = None


class BullMarketStatsResponse(BaseModel):
    threshold: float
    items: list[BullMarketItem]
    total_days: int


class TurnoverRankingItem(BaseModel):
    rank: int
    date: str
    sh_amount: float | None = None
    sz_amount: float | None = None
    turnover: float | None = None


class TurnoverRankingResponse(BaseModel):
    top: int
    bull_market: str | None = None
    items: list[TurnoverRankingItem]


class StockRankingItem(BaseModel):
    rank: int
    date: str
    code: str
    name: str | None = None
    amount: float | None = None


class StockRankingResponse(BaseModel):
    top: int
    bull_market: str | None = None
    items: list[StockRankingItem]


class BullMarketMetaItem(BaseModel):
    name: str
    start: str
    end: str
    description: str | None = None


class BullMarketsMetaResponse(BaseModel):
    items: list[BullMarketMetaItem]
