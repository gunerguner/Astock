"""日期时间工具：统一 UTC ISO 串与上海本地日历日。"""

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def today_local() -> str:
    """上海时区当前日历日 YYYY-MM-DD（baostock 查询 end_date 等）。"""
    return datetime.now(_SHANGHAI).strftime("%Y-%m-%d")


def now_local() -> datetime:
    return datetime.now(_SHANGHAI)


def normalize_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    return text[:10]


def synced_today(last_synced_at: str | None) -> bool:
    """判断 last_synced_at 是否落在上海时区「今天」。"""
    if not last_synced_at:
        return False
    try:
        dt = datetime.fromisoformat(last_synced_at)
        if dt.tzinfo is not None:
            local_date = dt.astimezone(_SHANGHAI).date()
        else:
            local_date = dt.date()
        return local_date == now_local().date()
    except ValueError:
        return False
