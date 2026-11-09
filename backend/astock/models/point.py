from sqlalchemy import Index
from sqlmodel import SQLModel, Field


class Point(SQLModel, table=True):
    __tablename__ = "point"  # type: ignore[assignment]
    __table_args__ = (Index("idx_point_index_date", "index_code", "date"),)

    date: str = Field(primary_key=True)
    index_code: str = Field(primary_key=True)
    close: float
    cached_at: str
