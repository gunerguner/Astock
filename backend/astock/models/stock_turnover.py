from sqlmodel import Field, SQLModel
from sqlalchemy import Index


class StockTurnover(SQLModel, table=True):
    __tablename__ = "stock_turnover"
    __table_args__ = (
        Index("idx_stock_turnover_amount", "amount"),
    )

    date: str = Field(primary_key=True)
    code: str = Field(primary_key=True)
    name: str
    amount: float
    cached_at: str
