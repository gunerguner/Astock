"""美国宏观抓取公共工具。"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import httpx

from astock.config import EM_USER_AGENT
from astock.sources.retry import retry_call

HTTP_TIMEOUT = 30.0
FRED_HTTP_TIMEOUT = 6.0
DEFAULT_HEADERS = {
    "User-Agent": EM_USER_AGENT,
    "Accept": "text/csv,application/json,*/*",
}


def parse_period(value: Any) -> str | None:
    """解析为 YYYY-MM；支持 date/datetime/字符串。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace("/", "-")
    if len(text) >= 7 and text[4] == "-" and text[:7].replace("-", "").isdigit():
        return text[:7]
    for fmt, size in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y%m%d", 8), ("%Y%m", 6)):
        try:
            return datetime.strptime(text[:size], fmt).strftime("%Y-%m")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m")
    except ValueError:
        return None


def parse_iso_date(value: Any) -> str | None:
    """解析为 YYYY-MM-DD。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace("/", "-")
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%Y-%m", "%m/%d/%Y"):
        try:
            raw = text if fmt != "%Y-%m" else text[:7]
            dt = datetime.strptime(raw[:10] if fmt != "%Y-%m" else raw, fmt)
            if fmt == "%Y-%m":
                return dt.strftime("%Y-%m-01")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # M/D/YYYY
    try:
        parts = text.replace("-", "/").split("/")
        if len(parts) == 3:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
    except (TypeError, ValueError):
        pass
    return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def http_get_text(
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> str:
    def _do() -> str:
        with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS, http2=False) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.text

    return retry_call(label, _do)


def http_get_json(
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> Any:
    def _do() -> Any:
        with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS, http2=False) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    return retry_call(label, _do)


def month_end(period: str) -> str:
    """YYYY-MM → 该月最后一天 YYYY-MM-DD。"""
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt.fromordinal(nxt.toordinal() - 1)).isoformat()
