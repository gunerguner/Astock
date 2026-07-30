"""中国消费者信心指数（东财 akshare）。"""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak

from astock.models.macro import METRIC_CONSUMER_CONFIDENCE, REGION_CN
from astock.sources.cn_macro._common import parse_cn_month, to_float
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.market_overview._common import safe_retry_df

logger = logging.getLogger(__name__)


def fetch_consumer_confidence() -> SourceFetchResult:
    """AKShare macro_china_xfzxx → 消费者信心指数。"""
    df = safe_retry_df("macro_china_xfzxx", ak.macro_china_xfzxx, logger=logger)
    if df is None or df.empty:
        return SourceFetchResult.failure("东财消费者信心：空结果")

    records: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_cn_month(raw.get("月份"))
        value = to_float(raw.get("消费者信心指数-指数值"))
        if not period or value is None:
            continue
        records.append(
            {
                "region": REGION_CN,
                "period": period,
                "metric": METRIC_CONSUMER_CONFIDENCE,
                "value": round(float(value), 4),
            }
        )
    records.sort(key=lambda r: r["period"])
    if not records:
        return SourceFetchResult.failure("东财消费者信心：无有效数据")
    return SourceFetchResult(records=records, ok=True)
