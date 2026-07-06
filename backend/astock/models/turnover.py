from sqlmodel import SQLModel, Field


class Turnover(SQLModel, table=True):
    __tablename__ = "turnover"

    date: str = Field(primary_key=True)
    sh_amount: float | None = None
    sz_amount: float | None = None
    cyb_amount: float | None = None
    turnover: float | None = None
    cached_at: str | None = None
