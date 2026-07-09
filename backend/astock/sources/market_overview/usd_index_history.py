"""美元指数历史日线（东财 push2his + akshare 兜底）。"""

import logging
import time

import akshare as ak
import httpx
import pandas as pd

from astock.config import EM_HIST_HOSTS, USD_HISTORY_TIMEOUT
from astock.core.datetime_utils import normalize_date
from astock.sources.market_overview._common import (
    _em_udi_headers,
    _parse_em_kline_lines,
    _tail_closes,
)

logger = logging.getLogger(__name__)


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


def fetch_usd_index_history(n: int) -> dict[str, float]:
    """东财 push2his 日线历史，多 host 快速轮询 + akshare 兜底。"""
    for host in EM_HIST_HOSTS:
        try:
            closes = _fetch_usd_index_history_em(host, n)
            if closes:
                return closes
        except Exception as e:
            logger.warning("美元指数历史(%s)失败: %s", host, e)
    return _fetch_usd_index_history_akshare(n)
