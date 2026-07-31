from pydantic import BaseModel


class BullMarketItem(BaseModel):
    market: str
    start: str
    end: str
    description: str = ""
    days: int
    max_value: float | None = None
    not_available: bool = False


class BullMarketStatsResponse(BaseModel):
    threshold: float
    items: list[BullMarketItem]
    total_days: int


class IndexPointStats(BaseModel):
    index_code: str
    index_name: str
    threshold: float
    items: list[BullMarketItem]
    total_days: int


class MultiIndexPointStatsResponse(BaseModel):
    indices: list[IndexPointStats]


class TurnoverRankingItem(BaseModel):
    rank: int
    date: str
    sse_amount: float
    szse_amount: float
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


PriceLevelRow = PriceLevelItem | PriceLevelPendingItem


class PriceLevelsResponse(BaseModel):
    last_synced_at: str | None = None
    as_of: str
    latest_trading_date: str
    items: list[PriceLevelRow]
    cache_errors: list[str] = []


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
    period_start: str
    period_end: str


MarketOverviewRow = MarketOverviewItem | MarketOverviewErrorItem


class MarketOverviewCategory(BaseModel):
    key: str
    name: str
    items: list[MarketOverviewRow]


class MarketOverviewResponse(BaseModel):
    as_of: str
    latest_trading_date: str
    categories: list[MarketOverviewCategory]
    errors: list[str] = []


class UsMacroPointItem(BaseModel):
    period: str
    cpi_yoy: float | None = None
    fed_rate_upper: float | None = None


class UsMacroResponse(BaseModel):
    start: str
    latest_period: str | None = None
    last_synced_at: str | None = None
    points: list[UsMacroPointItem]


class CnMacroPointItem(BaseModel):
    period: str
    cpi_yoy: float | None = None
    ppi_yoy: float | None = None
    pmi_manufacturing: float | None = None
    pmi_non_manufacturing: float | None = None
    consumer_confidence: float | None = None


class CnMacroResponse(BaseModel):
    start: str
    latest_period: str | None = None
    last_synced_at: str | None = None
    points: list[CnMacroPointItem]

