from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class Turnover(SQLModel, table=True):
    __tablename__ = "turnover"
    __table_args__ = (Index("idx_turnover_turnover", "turnover"),)

    date: str = Field(primary_key=True)
    sse_amount: float  # 上交所全市场成交额
    szse_amount: float  # 深交所全市场成交额
    turnover: float  # sse_amount + szse_amount
    cached_at: str
