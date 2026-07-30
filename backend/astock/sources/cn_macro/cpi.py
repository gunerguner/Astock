"""中国 CPI / PPI 同比：东财（akshare）。"""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak

from astock.models.macro import METRIC_CPI_YOY, METRIC_PPI_YOY, REGION_CN
from astock.sources.cn_macro._common import parse_cn_month, to_float
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.market_overview._common import safe_retry_df

logger = logging.getLogger(__name__)


def _records_from_df(
    df: Any,
    *,
    month_col: str,
    value_col: str,
    metric: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_cn_month(raw.get(month_col))
        value = to_float(raw.get(value_col))
        if not period or value is None:
            continue
        out.append(
            {
                "region": REGION_CN,
                "period": period,
                "metric": metric,
                "value": round(float(value), 4),
            }
        )
    out.sort(key=lambda r: r["period"])
    return out


def fetch_cpi() -> SourceFetchResult:
    """AKShare macro_china_cpi → 全国 CPI 同比 %。"""
    df = safe_retry_df("macro_china_cpi", ak.macro_china_cpi, logger=logger)
    if df is None or df.empty:
        return SourceFetchResult.failure("东财 CPI：空结果")

    records = _records_from_df(
        df,
        month_col="月份",
        value_col="全国-同比增长",
        metric=METRIC_CPI_YOY,
    )
    if not records:
        return SourceFetchResult.failure("东财 CPI：无有效同比数据")
    return SourceFetchResult(records=records, ok=True)


def fetch_ppi() -> SourceFetchResult:
    """AKShare macro_china_ppi → PPI 同比 %。"""
    df = safe_retry_df("macro_china_ppi", ak.macro_china_ppi, logger=logger)
    if df is None or df.empty:
        return SourceFetchResult.failure("东财 PPI：空结果")

    records = _records_from_df(
        df,
        month_col="月份",
        value_col="当月同比增长",
        metric=METRIC_PPI_YOY,
    )
    if not records:
        return SourceFetchResult.failure("东财 PPI：无有效同比数据")
    return SourceFetchResult(records=records, ok=True)
