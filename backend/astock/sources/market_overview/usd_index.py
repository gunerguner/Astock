"""美元指数抓取：日线历史为主，现货仅补最新结算日。"""

import json
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
    MARKET_OVERVIEW_RECENT_DAYS,
    USD_HISTORY_TIMEOUT,
    USD_SPOT_TIMEOUT,
    WEEKLY_BASELINE_OFFSET,
)
from astock.core.datetime_utils import last_settled_date, normalize_date, now_local
from astock.core.price_utils import has_sufficient_baseline_points
from astock.sources.market_overview._common import (
    em_udi_headers,
    merge_close_dicts,
    parse_em_kline_lines,
    tail_closes,
    df_to_tail_closes,
)

logger = logging.getLogger(__name__)
_SINA_DINIW_REFERER = "https://finance.sina.com.cn/money/forex/hq/DINIW.shtml"
_SINA_DINIW_DAY_K_URL = (
    "https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/"
    "var_DINIW=/NewForexService.getDayKLine?symbol=DINIW"
)


def _previous_weekday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _spot_pairs_to_closes(
    quote_date: str,
    current: float,
    prev: float | None,
    *,
    scale: float = 1.0,
) -> dict[str, float]:
    pairs: list[tuple[str, float]] = [(quote_date, current * scale)]
    if prev is not None and not pd.isna(prev):
        pairs.insert(0, (_previous_weekday(quote_date), float(prev) * scale))
    return tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS, market="us")


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
            return {}

        current = pd.to_numeric(row.get("f2"), errors="coerce")
        prev = pd.to_numeric(row.get("f18"), errors="coerce")
        if pd.isna(current):
            return {}

        ts_raw = row.get("f124")
        today = (
            datetime.fromtimestamp(int(ts_raw)).strftime("%Y-%m-%d")
            if ts_raw
            else now_local().strftime("%Y-%m-%d")
        )
        return _spot_pairs_to_closes(
            today, float(current), float(prev) if pd.notna(prev) else None, scale=0.01
        )


def _fetch_usd_index_spot_sina() -> dict[str, float]:
    headers = {"User-Agent": EM_USER_AGENT, "Referer": _SINA_DINIW_REFERER}
    with httpx.Client(timeout=USD_SPOT_TIMEOUT, headers=headers, http2=False) as client:
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
    return _spot_pairs_to_closes(
        quote_date, float(current), float(prev) if pd.notna(prev) else None
    )


def _fetch_usd_index_spot() -> dict[str, float]:
    """现货仅作补丁：优先新浪（字段更完整），东财次之。"""
    for fetcher in (_fetch_usd_index_spot_sina, _fetch_usd_index_spot_em):
        try:
            closes = fetcher()
            if closes:
                return closes
        except Exception as e:
            logger.warning("美元指数现货失败(%s): %s", fetcher.__name__, e)
    return {}


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
        timeout=USD_HISTORY_TIMEOUT, headers=em_udi_headers(), http2=False
    ) as client:
        resp = client.get(f"{host}/api/qt/stock/kline/get", params=params)
        resp.raise_for_status()
        klines = (resp.json().get("data") or {}).get("klines") or []
        return tail_closes(parse_em_kline_lines(klines), n, market="us")


def _fetch_usd_index_history_sina(n: int) -> dict[str, float]:
    """新浪 DINIW 日线（生产机东财/akshare 常被掐时的主兜底）。"""
    headers = {"User-Agent": EM_USER_AGENT, "Referer": _SINA_DINIW_REFERER}
    with httpx.Client(timeout=USD_HISTORY_TIMEOUT, headers=headers, http2=False) as client:
        resp = client.get(_SINA_DINIW_DAY_K_URL)
        resp.raise_for_status()
        text = resp.text
    match = re.search(r"var_DINIW=\((.*)\)\s*;?\s*$", text, re.S)
    if not match:
        return {}
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
    closes = tail_closes(pairs, n, market="us")
    if closes:
        logger.info("美元指数历史来自新浪 DINIW: %s 点", len(closes))
    return closes


def _fetch_usd_index_history_akshare(n: int) -> dict[str, float]:
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
        closes = df_to_tail_closes(df, n, date_col="日期", value_col="收盘", market="us")
        if closes:
            logger.info("美元指数历史来自 akshare: %s 点", len(closes))
            return closes
    return {}


def _fetch_usd_index_history(n: int) -> dict[str, float]:
    """历史顺序：新浪日线（生产可达）→ akshare → 东财 push2his。"""
    for fetcher, label in (
        (_fetch_usd_index_history_sina, "sina"),
        (_fetch_usd_index_history_akshare, "akshare"),
    ):
        try:
            closes = fetcher(n)
            if closes:
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", label, e)

    for host in EM_HIST_HOSTS:
        try:
            closes = _fetch_usd_index_history_em(host, n)
            if closes:
                logger.info("美元指数历史来自东财 %s: %s 点", host, len(closes))
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", host, e)
    return {}


def _needs_spot_patch(history: dict[str, float]) -> bool:
    """历史已覆盖结算日且基准点够时不打现货，减少生产机对不稳定接口的依赖。"""
    if not history:
        return True
    if not has_sufficient_baseline_points(history, market="us"):
        return True
    return max(history) < last_settled_date("us")


def fetch_usd_index(n: int) -> dict[str, float]:
    """日线历史为主；现货仅在历史缺最新结算日或点数不足时补丁合并。"""
    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)
    history = _fetch_usd_index_history(history_n)

    spot: dict[str, float] = {}
    if _needs_spot_patch(history):
        spot = _fetch_usd_index_spot()

    if not history and not spot:
        return {}

    if not spot:
        return history

    merged = merge_close_dicts(history, spot, n=n, market="us")
    if has_sufficient_baseline_points(merged, market="us"):
        return merged

    # 现货补丁仍不够：再拉更长历史一次
    longer = _fetch_usd_index_history(history_n + 10)
    if longer:
        merged = merge_close_dicts(longer, spot, n=n, market="us")
    return merged
