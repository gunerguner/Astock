"""中国宏观抓取公共工具。"""

from __future__ import annotations

import re
from typing import Any

from astock.sources.us_macro._common import parse_period, to_float

__all__ = ["parse_cn_month", "parse_period", "to_float"]

_CN_MONTH_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")


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
