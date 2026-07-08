"""分析查询公共工具。"""

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlmodel import Session, SQLModel, select

from astock.config import BULL_MARKETS
from astock.core.exceptions import AppError
from astock.schemas.analysis import BullMarketItem


def get_bull_market_period(bull_market: str | None) -> tuple[str, str] | None:
    if not bull_market or bull_market == "all":
        return None
    period = BULL_MARKETS.get(bull_market)
    if period is None:
        raise ValueError(f"未知牛市区间: {bull_market}")
    return period["start"], period["end"]


def require_rows(db: Session, model: type[SQLModel], empty_message: str) -> None:
    exists = db.exec(select(model).limit(1)).first()
    if exists is None:
        raise AppError(message=empty_message)


def empty_index_items(available_from: str | None = None) -> list[BullMarketItem]:
    items: list[BullMarketItem] = []
    for market_name, period in BULL_MARKETS.items():
        not_available = bool(available_from and available_from > period["end"])
        items.append(
            BullMarketItem(
                market=market_name,
                start=period["start"],
                end=period["end"],
                description=period.get("description"),
                days=0,
                max_value=None,
                not_available=not_available,
            )
        )
    items.sort(key=lambda x: x.end, reverse=True)
    return items
