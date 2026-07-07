"""akshare 数据源：美股复权历史、外盘期货历史。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import akshare as ak
import pandas as pd

from astock.config import GLOBAL_ASSETS
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _normalize_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    return text[:10]


def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = out["date"].map(_normalize_date)
    for col in ("open", "high", "low", "close"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "close", "high"])
    out = out.sort_values("date").reset_index(drop=True)
    return out


def fetch_stock_history(ticker: str) -> pd.DataFrame:
    try:
        df = ak.stock_us_daily(symbol=ticker, adjust="qfq")
    except ValueError as e:
        # akshare 已知缺陷：新股(刚上市、无复权因子历史)在计算前复权时,
        # 新浪只返回1行复权因子,导致其内部对只读 pandas 索引赋值报错。
        # 新股本身没有拆股/分红事件,未复权价格即为真实价格,直接回退即可。
        if "read-only" not in str(e):
            raise
        logger.warning("%s 前复权计算失败(akshare 已知缺陷,新股无复权因子)，回退未复权数据", ticker)
        df = ak.stock_us_daily(symbol=ticker, adjust="")
    return _normalize_history_df(df)


def fetch_commodity_history(code: str) -> pd.DataFrame:
    df = ak.futures_foreign_hist(symbol=code)
    return _normalize_history_df(df)


def fetch_asset_history(ticker: str, asset_type: str) -> pd.DataFrame:
    if asset_type == "stock":
        return fetch_stock_history(ticker)
    return fetch_commodity_history(ticker)


def extract_ath(df: pd.DataFrame) -> tuple[float, str] | None:
    if df.empty:
        return None
    idx = df["high"].astype(float).idxmax()
    row = df.loc[idx]
    return float(row["high"]), _normalize_date(row["date"])


def extract_recent_closes(df: pd.DataFrame, n: int = 10) -> dict[str, float]:
    if df.empty:
        return {}
    tail = df.tail(n)
    return {
        _normalize_date(row["date"]): float(row["close"])
        for _, row in tail.iterrows()
    }


def fetch_one_asset(asset: dict[str, str]) -> tuple[str, SourceFetchResult]:
    ticker = asset["ticker"]
    if asset.get("data_pending"):
        return ticker, SourceFetchResult(
            records=[],
            ok=False,
            errors=[f"{ticker}: 待接入数据源"],
        )
    asset_type = asset["asset_type"]
    try:
        df = fetch_asset_history(ticker, asset_type)
        if df.empty:
            return ticker, SourceFetchResult(
                records=[],
                ok=False,
                errors=[f"{ticker} 历史数据为空"],
            )
        ath = extract_ath(df)
        if ath is None:
            return ticker, SourceFetchResult(
                records=[],
                ok=False,
                errors=[f"{ticker} 无法提取历史最高点"],
            )
        all_time_high, ath_date = ath
        recent_closes = extract_recent_closes(df)
        return ticker, SourceFetchResult(
            records=[
                {
                    "all_time_high": all_time_high,
                    "ath_date": ath_date,
                    "recent_closes": recent_closes,
                }
            ],
            ok=True,
        )
    except Exception as e:
        logger.warning("抓取 %s 失败: %s", ticker, e)
        return ticker, SourceFetchResult(
            records=[],
            ok=False,
            errors=[f"{ticker}: {e}"],
        )


def fetch_all_assets(
    assets: list[dict[str, str]] | None = None,
) -> dict[str, SourceFetchResult]:
    assets = assets or GLOBAL_ASSETS
    results: dict[str, SourceFetchResult] = {}
    # 串行抓取：akshare 底层依赖 mini_racer（V8），
    # 多线程并发初始化 V8 configurable pool 会在 macOS 上触发 fatal crash。
    for asset in assets:
        ticker, result = fetch_one_asset(asset)
        results[ticker] = result
    return results
