from sqlmodel import Field, SQLModel


class AssetHigh(SQLModel, table=True):
    __tablename__ = "asset_high"

    ticker: str = Field(primary_key=True)
    name: str
    asset_type: str
    all_time_high: float
    ath_date: str
    cached_at: str
