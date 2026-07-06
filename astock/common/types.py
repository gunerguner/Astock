from typing import Literal, TypedDict


class TurnoverRecord(TypedDict):
    date: str
    sh_amount: float
    sz_amount: float
    cyb_amount: float
    turnover: float
    cached_at: str


class PointRecord(TypedDict):
    date: str
    close: float
    cached_at: str


class StockTurnoverRecord(TypedDict):
    date: str
    code: str
    name: str
    amount: float
    cached_at: str


class BigCapStock(TypedDict):
    code: str
    name: str
    market_cap: float


ImportStatus = Literal["success", "partial_failure", "failed"]
