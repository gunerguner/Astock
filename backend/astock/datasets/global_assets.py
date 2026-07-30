"""全球资产历史、ATH、近期收盘价数据集。"""

from __future__ import annotations

import logging

import pandas as pd

from astock.config import GLOBAL_ASSETS
from astock.core.datetime_utils import last_settled_date, market_for_asset_type, normalize_date
from astock.datasets.result import FetchResult
from astock.providers.akshare.assets import fetch_asset_history

logger = logging.getLogger(__name__)

__all__ = ["fetch_all_assets"]


def _extract_ath(df: pd.DataFrame) -> tuple[float, str] | None:
    if df.empty:
        return None
    idx = df["high"].astype(float).idxmax()
    row = df.loc[idx]
    return float(row["high"]), normalize_date(row["date"])


def _extract_recent_closes(
    df: pd.DataFrame,
    n: int = 10,
    *,
    market: str = "cn",
) -> dict[str, float]:
    if df.empty:
        return {}
    cap = last_settled_date(market)
    df = df[df["date"] <= cap]
    if df.empty:
        return {}
    tail = df.tail(n)
    return {
        normalize_date(row["date"]): float(row["close"])
        for _, row in tail.iterrows()
    }


def _fetch_one_asset(asset: dict[str, str]) -> tuple[str, FetchResult]:
    ticker = asset["ticker"]
    if asset.get("data_pending"):
        return ticker, FetchResult.failure(f"{ticker}: 待接入数据源")
    asset_type = asset["asset_type"]
    try:
        df = fetch_asset_history(ticker, asset_type)
        if df.empty:
            return ticker, FetchResult.failure(f"{ticker} 历史数据为空")
        ath = _extract_ath(df)
        if ath is None:
            return ticker, FetchResult.failure(f"{ticker} 无法提取历史最高点")
        all_time_high, ath_date = ath
        recent_closes = _extract_recent_closes(
            df, market=market_for_asset_type(asset_type)
        )
        return ticker, FetchResult(
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
        return ticker, FetchResult.failure(f"{ticker}: {e}")


def fetch_all_assets(
    assets: list[dict[str, str]] | None = None,
) -> dict[str, FetchResult]:
    assets = assets or GLOBAL_ASSETS
    results: dict[str, FetchResult] = {}
    # 故意串行：akshare 底层 mini_racer 多线程会在 macOS 上 fatal crash。
    for asset in assets:
        ticker, result = _fetch_one_asset(asset)
        results[ticker] = result
    return results
