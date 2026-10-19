"""交易日历：以 exchange_calendars 判定各市场交易日。

对齐 stockManager：A 股 XSHG、美股 XNYS，覆盖周末与交易所休市日。
"""

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
            if cal.is_session(check):
                return check.isoformat()
            check -= timedelta(days=1)

        raise RuntimeError(
            f"未找到 {market} 在 {day} 前 {_MAX_LOOKBACK_DAYS} 天内的交易日"
        )

    @classmethod
    def sessions_on_or_between(
        cls,
        start: str,
        end: str,
        market: MarketCode = "cn",
    ) -> list[str]:
        """返回 [start, end] 闭区间内的交易日（YYYY-MM-DD），两端可落在休市日。"""
        cal = cls.get(market)
        start_d = datetime.strptime(str(start)[:10], "%Y-%m-%d").date()
        end_d = datetime.strptime(str(end)[:10], "%Y-%m-%d").date()
        if start_d > end_d:
            return []
        if not cal.is_session(start_d):
            nxt = cal.date_to_session(start_d, direction="next")
            start_d = datetime.strptime(str(pd.Timestamp(nxt))[:10], "%Y-%m-%d").date()
        if not cal.is_session(end_d):
            end_d = datetime.strptime(
                cls.previous_session_on_or_before(end, market),
                "%Y-%m-%d",
            ).date()
        if start_d > end_d:
            return []
        return [ts.strftime("%Y-%m-%d") for ts in cal.sessions_in_range(start_d, end_d)]
