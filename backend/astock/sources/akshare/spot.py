"""akshare 全市场个股快照。"""

import logging
import re

import akshare as ak
import pandas as pd

from astock.sources.fetch_result import SourceFetchResult
from astock.sources.symbols import is_a_share_code

logger = logging.getLogger(__name__)


def _parse_spot_dataframe(df: pd.DataFrame) -> list[dict]:
    """将东财/akshare 全市场快照 DataFrame 规范为 {code, name, amount, market_cap}。"""
    col_map = {
        "代码": "code",
        "名称": "name",
        "成交额": "amount",
        "总市值": "market_cap",
    }
    missing = [c for c in col_map if c not in df.columns]
    if missing:
        raise ValueError(f"快照缺少列: {missing}; 实际列={list(df.columns)}")

    out = df[list(col_map.keys())].rename(columns=col_map).copy()
    out["name"] = out["name"].astype(str).fillna("")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
    out["market_cap"] = pd.to_numeric(out["market_cap"], errors="coerce")
    out = out.dropna(subset=["amount", "market_cap"])
    records: list[dict] = []
    for row in out.to_dict("records"):
        raw_code = str(row["code"]).strip()
        if raw_code.endswith(".0"):
            raw_code = raw_code[:-2]
        digits = re.sub(r"\D", "", raw_code)
        if len(digits) != 6 or not is_a_share_code(digits):
            continue
        records.append(
            {
                "code": digits,
                "name": str(row["name"]),
                "amount": float(row["amount"]),
                "market_cap": float(row["market_cap"]),
            }
        )
    return records


def fetch_stock_spot_snapshot() -> SourceFetchResult:
    """全市场个股快照（代码/名称/成交额/总市值，单位元）。

    主路径：akshare `stock_zh_a_spot_em`（东财一次拉全市场）。
    失败时由调用方回退腾讯批量。
    """
    try:
        raw = ak.stock_zh_a_spot_em()
    except Exception as e:
        msg = f"全市场个股快照失败(akshare): {e}"
        logger.warning(msg)
        return SourceFetchResult.failure(msg)

    if raw is None or raw.empty:
        return SourceFetchResult.failure("全市场个股快照为空(akshare)")

    try:
        records = _parse_spot_dataframe(raw)
    except Exception as e:
        msg = f"全市场个股快照解析失败(akshare): {e}"
        logger.warning(msg)
        return SourceFetchResult.failure(msg)

    if not records:
        return SourceFetchResult.failure("全市场个股快照无有效 A 股记录(akshare)")

    logger.info("全市场个股快照完成(akshare): %s 只", len(records))
    return SourceFetchResult(records=records)
