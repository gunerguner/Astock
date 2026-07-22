"""akshare 全球资产（美股/贵金属）历史与 ATH。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import GLOBAL_ASSETS
from astock.core.datetime_utils import last_settled_date, market_for_asset_type, normalize_date
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.retry import retry_call

logger = logging.getLogger(__name__)


def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" not in out.columns:
        return pd.DataFrame()
    out["date"] = out["date"].map(normalize_date)
    for col in ("open", "high", "low", "close"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["date", "close", "high"])
    out = out.sort_values("date").reset_index(drop=True)
    return out


def _fetch_stock_history(ticker: str) -> pd.DataFrame:
    try:
        df = ak.stock_us_daily(symbol=ticker, adjust="qfq")
    except ValueError as e:
        # akshare 已知缺陷：新股无复权因子时前复权会报错，回退未复权。
        if "read-only" not in str(e):
            raise
        logger.warning("%s 前复权计算失败(akshare 已知缺陷,新股无复权因子)，回退未复权数据", ticker)
        df = ak.stock_us_daily(symbol=ticker, adjust="")
    return _normalize_history_df(df)


def fetch_commodity_history(code: str) -> pd.DataFrame:
    """外盘期货/贵金属历史（市场概览 foreign_futures 也会直接调用）。"""
    df = retry_call(
        f"futures_foreign_hist:{code}",
        lambda: ak.futures_foreign_hist(symbol=code),
    )
    return _normalize_history_df(df)


def _fetch_asset_history(ticker: str, asset_type: str) -> pd.DataFrame:
    if asset_type == "stock":
        return _fetch_stock_history(ticker)
    return fetch_commodity_history(ticker)


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


def _fetch_one_asset(asset: dict[str, str]) -> tuple[str, SourceFetchResult]:
    ticker = asset["ticker"]
    if asset.get("data_pending"):
        return ticker, SourceFetchResult.failure(f"{ticker}: 待接入数据源")
    asset_type = asset["asset_type"]
    try:
        df = _fetch_asset_history(ticker, asset_type)
        if df.empty:
            return ticker, SourceFetchResult.failure(f"{ticker} 历史数据为空")
        ath = _extract_ath(df)
        if ath is None:
            return ticker, SourceFetchResult.failure(f"{ticker} 无法提取历史最高点")
        all_time_high, ath_date = ath
        recent_closes = _extract_recent_closes(df, market=market_for_asset_type(asset_type))
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
        return ticker, SourceFetchResult.failure(f"{ticker}: {e}")


def fetch_all_assets(
    assets: list[dict[str, str]] | None = None,
) -> dict[str, SourceFetchResult]:
    assets = assets or GLOBAL_ASSETS
    results: dict[str, SourceFetchResult] = {}
    # 故意串行：akshare 底层 mini_racer 多线程会在 macOS 上 fatal crash。
    for asset in assets:
        ticker, result = _fetch_one_asset(asset)
        results[ticker] = result
    return results
