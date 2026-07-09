"""美元指数抓取（境内数据源：东财 + 新浪）。"""

import logging
import re
import time
from datetime import datetime, timedelta

import akshare as ak
import httpx
import pandas as pd

from astock.config import (
    EM_DELAY_HOST,
    EM_HIST_HOSTS,
    EM_USER_AGENT,
    WEEKLY_BASELINE_OFFSET,
    MARKET_OVERVIEW_RECENT_DAYS,
    USD_HISTORY_TIMEOUT,
    USD_SPOT_TIMEOUT,
)
from astock.core.datetime_utils import normalize_date, now_local
from astock.services.price_utils import anchor_date_for_closes
from astock.sources.market_overview._common import (
    _em_udi_headers,
    _merge_close_dicts,
    _parse_em_kline_lines,
    _tail_closes,
)

logger = logging.getLogger(__name__)
_SINA_DINIW_REFERER = "https://finance.sina.com.cn/money/forex/hq/DINIW.shtml"


def _previous_weekday(date_str: str) -> str:
    """返回前一个工作日（跳过周末），用于现货快照昨收日期。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _fetch_usd_index_history_em(host: str, n: int) -> dict[str, float]:
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
        timeout=USD_HISTORY_TIMEOUT,
        headers=_em_udi_headers(),
        http2=False,
    ) as client:
        resp = client.get(f"{host}/api/qt/stock/kline/get", params=params)
        resp.raise_for_status()
        klines = (resp.json().get("data") or {}).get("klines") or []
        return _tail_closes(_parse_em_kline_lines(klines), n, market="us")


def _fetch_usd_index_history_akshare(n: int) -> dict[str, float]:
    """东财全球指数历史（akshare 封装，与 push2his 同口径）。"""
    for attempt in range(2):
        try:
            df = ak.index_global_hist_em(symbol="美元指数")
        except Exception as e:
            logger.warning("美元指数 akshare 历史第 %s 次失败: %s", attempt + 1, e)
            if attempt < 1:
                time.sleep(1.0)
            continue
        if df is None or df.empty or "日期" not in df.columns or "收盘" not in df.columns:
            return {}
        pairs: list[tuple[str, float]] = []
        for _, row in df.iterrows():
            d = normalize_date(row.get("日期"))
            close = pd.to_numeric(row.get("收盘"), errors="coerce")
            if d and pd.notna(close):
                pairs.append((d, float(close)))
        closes = _tail_closes(pairs, n, market="us")
        if closes:
            return closes
    return {}


def _fetch_usd_index_history(n: int) -> dict[str, float]:
    """东财 push2his 日线历史，多 host 快速轮询 + akshare 兜底。"""
    for host in EM_HIST_HOSTS:
        try:
            closes = _fetch_usd_index_history_em(host, n)
            if closes:
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", host, e)
    return _fetch_usd_index_history_akshare(n)


def _fetch_usd_index_spot_em() -> dict[str, float]:
    """东财 push2delay 现货快照。"""
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
    """新浪 hq.sinajs.cn 美元指数 DINIW 现货。"""
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


def _fetch_usd_index_spot() -> dict[str, float]:
    merged: dict[str, float] = {}
    for fetcher in (_fetch_usd_index_spot_em, _fetch_usd_index_spot_sina):
        try:
            closes = fetcher()
            if closes:
                merged = _merge_close_dicts(merged, closes, n=MARKET_OVERVIEW_RECENT_DAYS, market="us")
        except Exception as e:
            logger.warning("美元指数现货失败(%s): %s", fetcher.__name__, e)
    return merged


def fetch_usd_index(n: int) -> dict[str, float]:
    spot = _fetch_usd_index_spot()

    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)
    history = _fetch_usd_index_history(history_n)
    if not spot and not history:
        return {}

    merged = _merge_close_dicts(history, spot, n=n, market="us")
    anchor = anchor_date_for_closes(merged, "us")
    if anchor is None:
        return merged
    dates = [d for d in sorted(merged.keys()) if d <= anchor]
    if len(dates) >= required_points:
        return merged

    if history:
        history = _fetch_usd_index_history(history_n + 10)
        merged = _merge_close_dicts(history, spot, n=n, market="us")
    return merged
