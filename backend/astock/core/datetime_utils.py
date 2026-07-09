"""日期时间工具：统一 UTC ISO 串与各市场本地结算日。"""

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_NEW_YORK = ZoneInfo("America/New_York")

MarketCode = Literal["cn", "us"]
# A 股日线源（baostock/akshare）收盘后往往尚未就绪，傍晚后再视为「当日已结算」；
# 美股仍按本地收盘 16:00 计。
_MARKET_CLOSE_HOUR: dict[MarketCode, int] = {
    "cn": 20,
    "us": 16,
}

_MARKET_SOURCE: dict[str, MarketCode] = {
    "cn_index": "cn",
    "boc_forex": "cn",
    "us_bond": "cn",
    "global_index": "us",
    "foreign_futures": "us",
}


def iso_now() -> str:
    """返回当前 UTC 时间的 ISO 秒级字符串。"""
    return datetime.now(UTC).isoformat(timespec="seconds")


def today_local() -> str:
    """上海时区当前日历日 YYYY-MM-DD。"""
    return datetime.now(_SHANGHAI).strftime("%Y-%m-%d")


def market_for_source(source: str) -> MarketCode:
    """按数据源推断结算时区（A 股/在岸数据 vs 美股/外盘）。"""
    return _MARKET_SOURCE.get(source, "cn")


def market_for_asset_type(asset_type: str) -> MarketCode:
    """按资产类型推断适用结算市场（股票/贵金属走美股时区）。"""
    return "us" if asset_type in ("stock", "metal") else "cn"


def last_settled_date(market: MarketCode = "cn") -> str:
    """各市场本地时区下、最近一个已收盘交易日。

    cn：上海 20:00 后算当日已结算（避免收盘后日线源空窗）；
    us：美东 16:00 后算当日已结算。
    """
    tz = _NEW_YORK if market == "us" else _SHANGHAI
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    if now.hour >= _MARKET_CLOSE_HOUR[market]:
        return today
    return add_calendar_days(today, -1)


def filter_settled_closes(
    closes: dict[str, float],
    market: MarketCode = "cn",
) -> dict[str, float]:
    """按市场结算日上界过滤收盘价序列。"""
    cap = last_settled_date(market)
    return {d: v for d, v in closes.items() if d <= cap}


def is_synced_through_settled(
    last_synced_date: str | None,
    market: MarketCode = "cn",
) -> bool:
    """水位是否已覆盖该市场最近可结算日。"""
    return bool(last_synced_date) and last_synced_date >= last_settled_date(market)


def is_multi_market_synced(last_synced_date: str | None) -> bool:
    """全球资产等多市场数据集：中/美两侧水位均达标才跳过。"""
    return is_synced_through_settled(last_synced_date, "cn") and is_synced_through_settled(
        last_synced_date, "us"
    )


def now_local() -> datetime:
    """返回上海时区当前本地时间。"""
    return datetime.now(_SHANGHAI)


def add_calendar_days(date_str: str, days: int = 1) -> str:
    """日历日加减，返回 YYYY-MM-DD。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (dt + timedelta(days=days)).isoformat()


def normalize_date(value: Any) -> str:
    """将 datetime/date/字符串统一规范为 YYYY-MM-DD。"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    return text[:10]
