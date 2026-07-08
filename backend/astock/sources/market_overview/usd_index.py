"""美元指数抓取。"""

import logging
import time
from datetime import datetime, timedelta

import httpx
import pandas as pd

from astock.config import (
    EM_DELAY_HOST,
    EM_HIST_HOST,
    WEEKLY_BASELINE_OFFSET,
    MARKET_OVERVIEW_IGNORE_SYSTEM_PROXY,
    MARKET_OVERVIEW_RECENT_DAYS,
    USD_HISTORY_TIMEOUT,
    USD_SPOT_TIMEOUT,
)
from astock.core.datetime_utils import now_local, today_local
from astock.sources.market_overview._common import (
    _em_udi_headers,
    _merge_close_dicts,
    _parse_em_kline_lines,
    _tail_closes,
)

logger = logging.getLogger(__name__)


def _previous_weekday(date_str: str) -> str:
    """返回前一个工作日（跳过周末），用于现货快照昨收日期。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _anchor_date_excluding_today_for_closes(closes: dict[str, float]) -> str | None:
    """对单个标的，取 < today 的最后一个交易日，用于对齐服务层 anchor_date。"""
    if not closes:
        return None
    today = today_local()
    dates = [d for d in closes.keys() if d < today]
    if dates:
        return max(dates)
    return max(closes.keys())


def _fetch_usd_index_history(n: int) -> dict[str, float]:
    """东财 push2his 日线历史（偶发断连，Connection: close 可提高成功率）。"""
    params = {
        "secid": "100.UDI",
        "klt": "101",
        "fqt": "1",
        # 多取一些，避免刚好落在 T 附近导致后续按 anchor_date 过滤后点数不够
        "lmt": str(n + 15),
        "end": "20500000",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64",
        "ut": "f057cbcbce2a86e2866ab8877db1d059",
        "forcect": "1",
    }
    for attempt in range(4):
        try:
            with httpx.Client(
                timeout=USD_HISTORY_TIMEOUT,
                headers=_em_udi_headers(),
                http2=False,
                trust_env=not MARKET_OVERVIEW_IGNORE_SYSTEM_PROXY,
            ) as client:
                resp = client.get(f"{EM_HIST_HOST}/api/qt/stock/kline/get", params=params)
                resp.raise_for_status()
                klines = (resp.json().get("data") or {}).get("klines") or []
                closes = _tail_closes(_parse_em_kline_lines(klines), n)
                if closes:
                    return closes
        except Exception as e:
            logger.warning("美元指数历史第 %s 次失败: %s", attempt + 1, e)
            if attempt < 1:
                time.sleep(1.0 * (attempt + 1))
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
        with httpx.Client(
            timeout=USD_SPOT_TIMEOUT,
            headers=headers,
            http2=False,
            trust_env=not MARKET_OVERVIEW_IGNORE_SYSTEM_PROXY,
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
            return _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS)
    except Exception as e:
        logger.warning("美元指数现货失败: %s", e)
        return {}


def fetch_usd_index(n: int) -> dict[str, float]:
    spot = _fetch_usd_index_spot()

    # 按你的口径：T(上次交易日) / T-1(前一交易日) / T-5(5个交易日之前)。
    # 因此美元指数需要至少 WEEKLY_BASELINE_OFFSET=6 个交易日点位，才能计算日/周涨跌。
    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)

    last_history: dict[str, float] = {}
    for _ in range(2):
        history = _fetch_usd_index_history(history_n)
        last_history = history
        if not spot and not history:
            return {}

        merged = _merge_close_dicts(history, spot, n=n)
        anchor = _anchor_date_excluding_today_for_closes(merged)
        if anchor is None:
            continue
        dates = [d for d in sorted(merged.keys()) if d <= anchor]
        if len(dates) >= required_points:
            return merged

        # 历史点位仍不足：加大历史请求规模再试一次
        history_n += 10

    # 最终兜底：尽可能返回合并结果（若仍不足，则涨跌字段会自然为 null）
    merged = _merge_close_dicts(last_history, spot, n=n)
    return merged
