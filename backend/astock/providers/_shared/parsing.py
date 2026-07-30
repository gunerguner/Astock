"""日期、月份、数值解析。"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

_CN_MONTH_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")


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


def parse_cn_month(value: Any) -> str | None:
    """解析东财中文月份（如 2026年06月份）或通用日期为 YYYY-MM。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    match = _CN_MONTH_RE.search(text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"
    return parse_period(value)


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


def month_end(period: str) -> str:
    """YYYY-MM → 该月最后一天 YYYY-MM-DD。"""
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt.fromordinal(nxt.toordinal() - 1)).isoformat()
