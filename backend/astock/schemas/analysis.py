from typing import Union

from pydantic import BaseModel


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
    sh_amount: float
    sz_amount: float
    turnover: float


class TurnoverRankingResponse(BaseModel):
    top: int
    bull_market: str | None = None
    items: list[TurnoverRankingItem]


class StockRankingItem(BaseModel):
    rank: int
    date: str
    code: str
    name: str
    amount: float


class StockRankingResponse(BaseModel):
    top: int
    bull_market: str | None = None
    items: list[StockRankingItem]


class PriceLevelPendingItem(BaseModel):
    ticker: str
    name: str
    asset_type: str
    conclusion: str
    data_pending: bool = True


class PriceLevelItem(BaseModel):
    ticker: str
    name: str
    asset_type: str
    current_price: float
    all_time_high: float
    ath_date: str
    percentage_diff: float
    ath_days: int
    daily_change: float | None = None
    weekly_change: float | None = None
    conclusion: str


PriceLevelRow = Union[PriceLevelItem, PriceLevelPendingItem]


class PriceLevelsResponse(BaseModel):
    last_synced_at: str | None = None
    as_of: str
    latest_trading_date: str
    items: list[PriceLevelRow]
    cache_errors: list[str] | None = None


class MarketOverviewErrorItem(BaseModel):
    key: str
    name: str
    code: str
    error: str


class MarketOverviewItem(BaseModel):
    key: str
    name: str
    code: str
    current_price: float
    daily_change: float | None = None
    weekly_change: float | None = None
    period_start: str | None = None
    period_end: str | None = None


MarketOverviewRow = Union[MarketOverviewItem, MarketOverviewErrorItem]


class MarketOverviewCategory(BaseModel):
    key: str
    name: str
    items: list[MarketOverviewRow]


class MarketOverviewResponse(BaseModel):
    as_of: str
    latest_trading_date: str
    categories: list[MarketOverviewCategory]
    errors: list[str] | None = None

