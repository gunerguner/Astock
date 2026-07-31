"""东方财富 HTTP：美元指数现货与 K 线。"""


from datetime import datetime
from typing import Any

import httpx
import pandas as pd

from astock.config import (
    EM_DELAY_HOST,
    EM_UDI_REFERER,
    EM_USER_AGENT,
    USD_HISTORY_TIMEOUT,
    USD_SPOT_TIMEOUT,
)
from astock.core.datetime_utils import normalize_date, now_local


def em_udi_headers() -> dict[str, str]:
    return {
        "User-Agent": EM_USER_AGENT,
        "Referer": EM_UDI_REFERER,
        "Connection": "close",
    }


def parse_em_kline_lines(klines: list[str]) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        d = normalize_date(parts[0])
        close = pd.to_numeric(parts[2], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return pairs


def fetch_udi_spot() -> dict[str, Any] | None:
    """返回 {quote_date, current, prev}；失败返回 None。"""
    params = {
        "np": "2",
        "fltt": "1",
        "invt": "2",
        "fs": "i:100.UDI",
        "fields": "f12,f14,f2,f18,f124",
        "fid": "f3",
        "pn": "1",
        "pz": "10",
        "po": "1",
        "dect": "1",
        "wbp2u": "|0|0|0|web",
    }
    headers = {
        "User-Agent": EM_USER_AGENT,
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }
    with httpx.Client(timeout=USD_SPOT_TIMEOUT, headers=headers, http2=False) as client:
        resp = client.get(f"{EM_DELAY_HOST}/api/qt/clist/get", params=params)
        resp.raise_for_status()
        diff = (resp.json().get("data") or {}).get("diff")
        row: dict | None = None
        if isinstance(diff, dict) and diff:
            row = next(iter(diff.values()))
        elif isinstance(diff, list) and diff:
            row = diff[0]
        if not row or row.get("f12") != "UDI":
            return None

        current = pd.to_numeric(row.get("f2"), errors="coerce")
        prev = pd.to_numeric(row.get("f18"), errors="coerce")
        if pd.isna(current):
            return None

        ts_raw = row.get("f124")
        today = (
            datetime.fromtimestamp(int(ts_raw)).strftime("%Y-%m-%d")
            if ts_raw
            else now_local().strftime("%Y-%m-%d")
        )
        return {
            "quote_date": today,
            "current": float(current) * 0.01,
            "prev": float(prev) * 0.01 if pd.notna(prev) else None,
        }


def fetch_udi_history(host: str, n: int) -> list[tuple[str, float]]:
    """东财 push2his K 线 → [(date, close), ...]。"""
    params = {
        "secid": "100.UDI",
        "klt": "101",
        "fqt": "1",
        "lmt": str(n + 15),
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    with httpx.Client(
        timeout=USD_HISTORY_TIMEOUT, headers=em_udi_headers(), http2=False
    ) as client:
        resp = client.get(f"{host}/api/qt/stock/kline/get", params=params)
        resp.raise_for_status()
        klines = (resp.json().get("data") or {}).get("klines") or []
        return parse_em_kline_lines(klines)
