"""新浪 HTTP：美元指数现货与日线。"""


import json
import re
from typing import Any

import httpx
import pandas as pd

from astock.config import EM_USER_AGENT, USD_HISTORY_TIMEOUT, USD_SPOT_TIMEOUT
from astock.core.datetime_utils import normalize_date

_SINA_DINIW_REFERER = "https://finance.sina.com.cn/money/forex/hq/DINIW.shtml"
_SINA_DINIW_DAY_K_URL = (
    "https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/"
    "var_DINIW=/NewForexService.getDayKLine?symbol=DINIW"
)


def fetch_diniw_spot() -> dict[str, Any] | None:
    """返回 {quote_date, current, prev}；失败返回 None。"""
    headers = {"User-Agent": EM_USER_AGENT, "Referer": _SINA_DINIW_REFERER}
    with httpx.Client(timeout=USD_SPOT_TIMEOUT, headers=headers, http2=False) as client:
        resp = client.get("https://hq.sinajs.cn/", params={"list": "DINIW"}, headers=headers)
        resp.raise_for_status()
        text = resp.text
    match = re.search(r'hq_str_DINIW="([^"]*)"', text)
    if not match or not match.group(1):
        return None
    parts = match.group(1).split(",")
    if len(parts) < 11:
        return None

    current = pd.to_numeric(parts[1], errors="coerce")
    prev = pd.to_numeric(parts[8], errors="coerce")
    quote_date = normalize_date(parts[10])
    if pd.isna(current) or not quote_date:
        return None
    return {
        "quote_date": quote_date,
        "current": float(current),
        "prev": float(prev) if pd.notna(prev) else None,
    }


def fetch_diniw_day_k() -> list[tuple[str, float]]:
    """新浪 DINIW 日线 → [(date, close), ...]。"""
    headers = {"User-Agent": EM_USER_AGENT, "Referer": _SINA_DINIW_REFERER}
    with httpx.Client(timeout=USD_HISTORY_TIMEOUT, headers=headers, http2=False) as client:
        resp = client.get(_SINA_DINIW_DAY_K_URL)
        resp.raise_for_status()
        text = resp.text
    match = re.search(r"var_DINIW=\((.*)\)\s*;?\s*$", text, re.S)
    if not match:
        return []
    payload = match.group(1).strip()
    if payload.startswith('"') and payload.endswith('"'):
        payload = json.loads(payload)
    pairs: list[tuple[str, float]] = []
    for row in payload.split("|"):
        parts = [p.strip() for p in row.split(",") if p.strip()]
        if len(parts) < 5:
            continue
        d = normalize_date(parts[0])
        close = pd.to_numeric(parts[4], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return pairs
