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


class PriceLevelItem(BaseModel):
    ticker: str
    name: str
    asset_type: str
    current_price: float | None = None
    all_time_high: float | None = None
    ath_date: str | None = None
    percentage_diff: float | None = None
    ath_days: int | None = None
    daily_change: float | None = None
    weekly_change: float | None = None
    conclusion: str
    data_pending: bool | None = None


class PriceLevelsResponse(BaseModel):
    last_synced_at: str | None = None
    as_of: str
    latest_trading_date: str | None = None
    items: list[PriceLevelItem]
    cache_errors: list[str] | None = None


class MarketOverviewItem(BaseModel):
    key: str
    name: str
    code: str
    current_price: float | None = None
    daily_change: float | None = None
    weekly_change: float | None = None
    period_start: str | None = None
    period_end: str | None = None
    error: str | None = None


class MarketOverviewCategory(BaseModel):
    key: str
    name: str
    items: list[MarketOverviewItem]


class MarketOverviewResponse(BaseModel):
    as_of: str
    latest_trading_date: str | None = None
    categories: list[MarketOverviewCategory]
    errors: list[str] | None = None

