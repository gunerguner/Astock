"""美元指数抓取。"""

import logging
import time
from datetime import datetime, timedelta

import httpx
import pandas as pd

from astock.config import MARKET_OVERVIEW_RECENT_DAYS
from astock.core.datetime_utils import now_local
from astock.sources.market_overview._common import (
    _EM_DELAY_HOST,
    _EM_HIST_HOST,
    _em_udi_headers,
    _merge_close_dicts,
    _parse_em_kline_lines,
    _tail_closes,
)

logger = logging.getLogger(__name__)


def _fetch_usd_index_history(n: int) -> dict[str, float]:
    """东财 push2his 日线历史（偶发断连，Connection: close 可提高成功率）。"""
    params = {
        "secid": "100.UDI",
        "klt": "101",
        "fqt": "1",
        "lmt": str(n + 5),
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    for attempt in range(2):
        try:
            with httpx.Client(timeout=12, headers=_em_udi_headers(), http2=False) as client:
                resp = client.get(f"{_EM_HIST_HOST}/api/qt/stock/kline/get", params=params)
                resp.raise_for_status()
                klines = (resp.json().get("data") or {}).get("klines") or []
                closes = _tail_closes(_parse_em_kline_lines(klines), n)
                if closes:
                    return closes
        except Exception as e:
            logger.warning("美元指数历史第 %s 次失败: %s", attempt + 1, e)
            if attempt < 1:
                time.sleep(1.0)
    return {}


def _fetch_usd_index_spot() -> dict[str, float]:
    """东财 push2delay 现货快照（稳定可用，作为历史接口失败时的兜底）。"""
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
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    }
    try:
        with httpx.Client(timeout=15, headers=headers, http2=False) as client:
            resp = client.get(f"{_EM_DELAY_HOST}/api/qt/clist/get", params=params)
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
                prev_date = (
                    datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=1)
                ).isoformat()
                pairs.insert(0, (prev_date, float(prev) / 100.0))
            return _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS)
    except Exception as e:
        logger.warning("美元指数现货失败: %s", e)
        return {}


def fetch_usd_index(n: int) -> dict[str, float]:
    history = _fetch_usd_index_history(n)
    if len(history) >= 6:
        return history
    spot = _fetch_usd_index_spot()
    if not history and not spot:
        return {}
    merged = _merge_close_dicts(history, spot, n=n)
    if merged:
        return merged
    return spot or history
