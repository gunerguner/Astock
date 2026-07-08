from sqlmodel import SQLModel, Field


class Point(SQLModel, table=True):
    __tablename__ = "point"

    date: str = Field(primary_key=True)
    close: float
    cached_at: str
