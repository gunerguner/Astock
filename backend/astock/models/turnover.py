from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class Turnover(SQLModel, table=True):
    __tablename__ = "turnover"
    __table_args__ = (Index("idx_turnover_turnover", "turnover"),)

    date: str = Field(primary_key=True)
    sh_amount: float
    sz_amount: float
    cyb_amount: float
    turnover: float
    cached_at: str
