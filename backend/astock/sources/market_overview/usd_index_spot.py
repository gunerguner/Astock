"""美元指数现货快照（东财 delay + 新浪 DINIW）。"""

import logging
import re
from datetime import datetime, timedelta

import httpx
import pandas as pd

from astock.config import EM_DELAY_HOST, EM_USER_AGENT, MARKET_OVERVIEW_RECENT_DAYS, USD_SPOT_TIMEOUT
from astock.core.datetime_utils import normalize_date, now_local
from astock.sources.market_overview._common import _merge_close_dicts, _tail_closes

logger = logging.getLogger(__name__)
_SINA_DINIW_REFERER = "https://finance.sina.com.cn/money/forex/hq/DINIW.shtml"


def _previous_weekday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _fetch_usd_index_spot_em() -> dict[str, float]:
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
    with httpx.Client(
        timeout=USD_SPOT_TIMEOUT,
        headers=headers,
        http2=False,
    ) as client:
        resp = client.get(f"{EM_DELAY_HOST}/api/qt/clist/get", params=params)
        resp.raise_for_status()
        diff = (resp.json().get("data") or {}).get("diff")
        row: dict | None = None
        if isinstance(diff, dict) and diff:
            row = next(iter(diff.values()))
        elif isinstance(diff, list) and diff:
            row = diff[0]
        if not row or row.get("f12") != "UDI":
            return {}

        current = pd.to_numeric(row.get("f2"), errors="coerce")
        prev = pd.to_numeric(row.get("f18"), errors="coerce")
        if pd.isna(current):
            return {}

        ts_raw = row.get("f124")
        if ts_raw:
            today = datetime.fromtimestamp(int(ts_raw)).strftime("%Y-%m-%d")
        else:
            today = now_local().strftime("%Y-%m-%d")

        pairs: list[tuple[str, float]] = [(today, float(current) / 100.0)]
        if pd.notna(prev):
            prev_date = _previous_weekday(today)
            pairs.insert(0, (prev_date, float(prev) / 100.0))
        return _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS, market="us")


def _fetch_usd_index_spot_sina() -> dict[str, float]:
    headers = {
        "User-Agent": EM_USER_AGENT,
        "Referer": _SINA_DINIW_REFERER,
    }
    with httpx.Client(
        timeout=USD_SPOT_TIMEOUT,
        headers=headers,
        http2=False,
    ) as client:
        resp = client.get("https://hq.sinajs.cn/", params={"list": "DINIW"}, headers=headers)
        resp.raise_for_status()
        text = resp.text
    match = re.search(r'hq_str_DINIW="([^"]*)"', text)
    if not match or not match.group(1):
        return {}
    parts = match.group(1).split(",")
    if len(parts) < 11:
        return {}

    current = pd.to_numeric(parts[1], errors="coerce")
    prev = pd.to_numeric(parts[8], errors="coerce")
    quote_date = normalize_date(parts[10])
    if pd.isna(current) or not quote_date:
        return {}

    pairs: list[tuple[str, float]] = [(quote_date, float(current))]
    if pd.notna(prev):
        prev_date = _previous_weekday(quote_date)
        pairs.insert(0, (prev_date, float(prev)))
    return _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS, market="us")


def fetch_usd_index_spot() -> dict[str, float]:
    merged: dict[str, float] = {}
    for fetcher in (_fetch_usd_index_spot_em, _fetch_usd_index_spot_sina):
        try:
            closes = fetcher()
            if closes:
                merged = _merge_close_dicts(
                    merged, closes, n=MARKET_OVERVIEW_RECENT_DAYS, market="us"
                )
        except Exception as e:
            logger.warning("美元指数现货失败(%s): %s", fetcher.__name__, e)
    return merged
