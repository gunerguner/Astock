"""交易日历：以 exchange_calendars 判定各市场交易日。

对齐 stockManager：A 股 XSHG、美股 XNYS，覆盖周末与交易所休市日。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import ClassVar, Literal

import pandas as pd
from exchange_calendars import ExchangeCalendar, get_calendar

MarketCode = Literal["cn", "us"]

_EXCHANGE_CODE: dict[MarketCode, str] = {
    "cn": "XSHG",
    "us": "XNYS",
}

# 长假（含春节）通常远小于此；防御性上限避免死循环。
_MAX_LOOKBACK_DAYS = 30


class TradingCalendar:
    """按市场缓存的交易所日历。"""

    _calendars: ClassVar[dict[MarketCode, ExchangeCalendar]] = {}

    @classmethod
    def get(cls, market: MarketCode = "cn") -> ExchangeCalendar:
        if market not in cls._calendars:
            cls._calendars[market] = get_calendar(_EXCHANGE_CODE[market])
        return cls._calendars[market]

    @classmethod
    def is_trading_day(cls, day: date | datetime | str, market: MarketCode = "cn") -> bool:
        """是否为该市场交易日（非周末、非法定假日、非交易所休市）。"""
        return bool(cls.get(market).is_session(pd.Timestamp(day)))

    @classmethod
    def previous_session_on_or_before(
        cls,
        day: date | datetime | str,
        market: MarketCode = "cn",
    ) -> str:
        """返回 day 当日或之前最近一个交易日（YYYY-MM-DD）。"""
        if isinstance(day, datetime):
            check = day.date()
        elif isinstance(day, date):
            check = day
        else:
            check = datetime.strptime(str(day)[:10], "%Y-%m-%d").date()

        cal = cls.get(market)
        for _ in range(_MAX_LOOKBACK_DAYS):
            if cal.is_session(pd.Timestamp(check)):
                return check.isoformat()
            check -= timedelta(days=1)

        raise RuntimeError(
            f"未找到 {market} 在 {day} 前 {_MAX_LOOKBACK_DAYS} 天内的交易日"
        )
