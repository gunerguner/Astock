"""全球市场概览数据源：akshare 抓取并归一化为 recent_closes。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable, TypeVar

import akshare as ak
import httpx
import pandas as pd

from astock.config import MARKET_OVERVIEW_RECENT_DAYS

logger = logging.getLogger(__name__)

T = TypeVar("T")

_FETCH_RETRIES = 4
_FETCH_RETRY_DELAY = 2.0


def _retry_call(label: str, fn: Callable[[], T]) -> T:
    last: Exception | None = None
    for attempt in range(_FETCH_RETRIES):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < _FETCH_RETRIES - 1:
                logger.warning("%s 第 %s 次失败，重试: %s", label, attempt + 1, e)
                time.sleep(_FETCH_RETRY_DELAY * (attempt + 1))
    assert last is not None
    raise last

_US_BOND_COLUMN_MAP = {
    "us_bond_5y": "美国国债收益率5年",
    "us_bond_10y": "美国国债收益率10年",
    "us_bond_30y": "美国国债收益率30年",
}

_GLOBAL_INDEX_SINA_FALLBACK = {
    "道琼斯": ".DJI",
    "标普500": ".INX",
    "纳斯达克": ".IXIC",
}

_GLOBAL_INDEX_EM_ONLY = {"美元指数"}

_CN_INDEX_LOOKBACK_DAYS = 180


def _normalize_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    return text[:10]


def _tail_closes(date_close_pairs: list[tuple[str, float]], n: int) -> dict[str, float]:
    if not date_close_pairs:
        return {}
    sorted_pairs = sorted(date_close_pairs, key=lambda x: x[0])
    return dict(sorted_pairs[-n:])


def _cn_index_sina_symbol(code: str) -> str:
    code = code.strip()
    prefix = "sz" if code.startswith("399") else "sh"
    return f"{prefix}{code}"


_EM_HIST_HOST = "https://push2his.eastmoney.com"
_EM_DELAY_HOST = "https://push2delay.eastmoney.com"
_EM_UDI_REFERER = "https://quote.eastmoney.com/gb/zsUDI.html"


def _em_udi_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": _EM_UDI_REFERER,
        "Connection": "close",
    }


def _parse_em_kline_lines(klines: list[str]) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        d = _normalize_date(parts[0])
        close = pd.to_numeric(parts[2], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return pairs


def _merge_close_dicts(*sources: dict[str, float], n: int) -> dict[str, float]:
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return _tail_closes(sorted(merged.items()), n)


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
            row: dict[str, Any] | None = None
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
                today = datetime.now().strftime("%Y-%m-%d")

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


def _fetch_usd_index(n: int) -> dict[str, float]:
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


def _fetch_global_index(symbol: str, n: int) -> dict[str, float]:
    sina_symbol = _GLOBAL_INDEX_SINA_FALLBACK.get(symbol)
    if sina_symbol:
        return _fetch_us_index_sina(sina_symbol, n)

    if symbol in _GLOBAL_INDEX_EM_ONLY:
        return _fetch_usd_index(n)

    logger.warning("未知全球指数: %s", symbol)
    return {}


def _fetch_us_index_sina(symbol: str, n: int) -> dict[str, float]:
    try:
        df = _retry_call(f"index_us_stock_sina:{symbol}", lambda: ak.index_us_stock_sina(symbol=symbol))
    except Exception as e:
        logger.warning("新浪美股指数 %s 失败: %s", symbol, e)
        return {}
    if df is None or df.empty:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = _normalize_date(row.get("date"))
        close = pd.to_numeric(row.get("close"), errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return _tail_closes(pairs, n)


def _fetch_cn_index(code: str, n: int) -> dict[str, float]:
    sina_symbol = _cn_index_sina_symbol(code)
    cutoff = datetime.now() - timedelta(days=_CN_INDEX_LOOKBACK_DAYS)
    try:
        raw = ak.stock_zh_index_daily(symbol=sina_symbol)
    except Exception as e:
        logger.warning("A股指数 %s 抓取失败: %s", code, e)
        return {}
    if raw is None or raw.empty:
        return {}
    df = raw.rename(columns={"date": "Date", "close": "Close"})
    if "Date" not in df.columns or "Close" not in df.columns:
        return {}
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df[df["Close"].notna()]
    df = df[df.index >= pd.Timestamp(cutoff.date())]
    pairs = [(d.strftime("%Y-%m-%d"), float(row["Close"])) for d, row in df.iterrows()]
    return _tail_closes(pairs, n)


def _fetch_foreign_futures(code: str, n: int) -> dict[str, float]:
    try:
        df = _retry_call(f"futures_foreign:{code}", lambda: ak.futures_foreign_hist(symbol=code))
    except Exception as e:
        logger.warning("外盘期货 %s 抓取失败: %s", code, e)
        return {}
    if df is None or df.empty or "date" not in df.columns or "close" not in df.columns:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = _normalize_date(row["date"])
        close = pd.to_numeric(row["close"], errors="coerce")
        if d and pd.notna(close):
            pairs.append((d, float(close)))
    return _tail_closes(pairs, n)


def _fetch_boc_forex(symbol: str, n: int) -> dict[str, float]:
    end = datetime.now()
    start = end - timedelta(days=_CN_INDEX_LOOKBACK_DAYS)
    try:
        df = ak.currency_boc_sina(
            symbol=symbol,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
    except Exception as e:
        logger.warning("中行汇率 %s 抓取失败: %s", symbol, e)
        return {}
    if df is None or df.empty:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        d = _normalize_date(row.get("日期"))
        # 央行中间价，单位：100 外币兑人民币，换算为元
        mid = pd.to_numeric(row.get("央行中间价"), errors="coerce")
        if d and pd.notna(mid):
            pairs.append((d, float(mid) / 100.0))
    return _tail_closes(pairs, n)


def _fetch_us_bond_rates() -> dict[str, dict[str, float]]:
    """一次调用返回 5/10/30 年美债 recent_closes。"""
    try:
        df = _retry_call("bond_zh_us_rate", ak.bond_zh_us_rate)
    except Exception as e:
        logger.warning("美债收益率抓取失败: %s", e)
        return {}
    if df is None or df.empty:
        return {}

    result: dict[str, dict[str, float]] = {}
    for code, col in _US_BOND_COLUMN_MAP.items():
        pairs: list[tuple[str, float]] = []
        for _, row in df.iterrows():
            d = _normalize_date(row.get("日期"))
            val = pd.to_numeric(row.get(col), errors="coerce")
            if d and pd.notna(val):
                pairs.append((d, float(val)))
        closes = _tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS)
        if closes:
            result[code] = closes
    return result


def fetch_item_closes(item: dict[str, str], n: int = MARKET_OVERVIEW_RECENT_DAYS) -> dict[str, float]:
    source = item["source"]
    code = item["code"]
    if source == "global_index":
        return _fetch_global_index(code, n)
    if source == "cn_index":
        return _fetch_cn_index(code, n)
    if source == "foreign_futures":
        return _fetch_foreign_futures(code, n)
    if source == "boc_forex":
        return _fetch_boc_forex(code, n)
    if source == "us_bond":
        # us_bond 由 fetch_all 批量处理
        return {}
    logger.warning("未知 source: %s", source)
    return {}


def fetch_all_items(
    items: list[dict[str, str]],
    n: int = MARKET_OVERVIEW_RECENT_DAYS,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """串行抓取全部资产，返回 {item_key: recent_closes} 与错误列表。"""
    all_closes: dict[str, dict[str, float]] = {}
    errors: list[str] = []

    us_bond_items = [it for it in items if it["source"] == "us_bond"]
    other_items = [it for it in items if it["source"] != "us_bond"]

    if us_bond_items:
        bond_rates = _fetch_us_bond_rates()
        for item in us_bond_items:
            key = item["key"]
            closes = bond_rates.get(item["code"], {})
            if closes:
                all_closes[key] = closes
            else:
                errors.append(f"{item['name']}({item['code']}): 美债数据为空")

    for item in other_items:
        key = item["key"]
        try:
            closes = fetch_item_closes(item, n)
            if closes:
                all_closes[key] = closes
            else:
                errors.append(f"{item['name']}({item['code']}): 数据为空")
        except Exception as e:
            logger.warning("抓取 %s 失败: %s", key, e)
            errors.append(f"{item['name']}({item['code']}): {e}")

    return all_closes, errors
