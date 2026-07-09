"""akshare 数据源：A股指数点位、美股复权历史、外盘期货历史。"""

import logging

import akshare as ak
import pandas as pd

from astock.config import GLOBAL_ASSETS, POINT_INDEX_CONFIG, START_DATE
from astock.core.datetime_utils import market_for_asset_type
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def _cn_index_sina_symbol(code: str) -> str:
    code = code.strip()
    prefix = "sz" if code.startswith("399") else "sh"
    return f"{prefix}{code}"


def fetch_cn_index_point(
    index_code: str, start_date: str | None = None
) -> SourceFetchResult:
    """通过 akshare（新浪）拉取 A 股指数日线收盘价。"""
    if index_code not in POINT_INDEX_CONFIG:
        return SourceFetchResult.failure(f"未知指数代码: {index_code}")

    config = POINT_INDEX_CONFIG[index_code]
    index_name = str(config["name"])
    start = start_date or START_DATE
    end = last_settled_date()
    sina_symbol = _cn_index_sina_symbol(index_code)

    try:
        raw = ak.stock_zh_index_daily(symbol=sina_symbol)
    except Exception as e:
        msg = f"{index_name}点位查询失败(akshare): {e}"
        logger.error(msg)
        return SourceFetchResult.failure(msg)

    if raw is None or raw.empty:
        logger.info("%s点位无新增数据(akshare): %s → %s", index_name, start, end)
        return SourceFetchResult.empty()

    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    if df.empty:
        logger.info("%s点位无有效数据(akshare): %s → %s", index_name, start, end)
        return SourceFetchResult.empty()

    cached_at = iso_now()
    records = [
        {
            "date": row["date"],
            "index_code": index_code,
            "close": float(row["close"]),
            "cached_at": cached_at,
        }
        for row in df.to_dict("records")
    ]
    logger.info(
        "%s点位拉取完成(akshare): %s 条 (%s → %s)",
        index_name,
        len(records),
        start,
        end,
    )
    return SourceFetchResult(records=records)


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
    return float(row["high"]), normalize_date(row["date"])


def extract_recent_closes(
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


def fetch_one_asset(asset: dict[str, str]) -> tuple[str, SourceFetchResult]:
    ticker = asset["ticker"]
    if asset.get("data_pending"):
        return ticker, SourceFetchResult.failure(f"{ticker}: 待接入数据源")
    asset_type = asset["asset_type"]
    try:
        df = fetch_asset_history(ticker, asset_type)
        if df.empty:
            return ticker, SourceFetchResult.failure(f"{ticker} 历史数据为空")
        ath = extract_ath(df)
        if ath is None:
            return ticker, SourceFetchResult.failure(f"{ticker} 无法提取历史最高点")
        all_time_high, ath_date = ath
        recent_closes = extract_recent_closes(df, market=market_for_asset_type(asset_type))
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
    # 故意串行、不启用并发：akshare 底层依赖 mini_racer（V8），
    # 多线程并发初始化 V8 configurable pool 会在 macOS 上触发 fatal crash。
    # 请勿添加 GLOBAL_ASSET_FETCH_WORKERS 类配置，当前架构不支持并行抓取。
    for asset in assets:
        ticker, result = fetch_one_asset(asset)
        results[ticker] = result
    return results
