"""中国 PMI：制造业 / 非制造业（东财 akshare）。"""

from __future__ import annotations

import logging
from typing import Any

import akshare as ak

from astock.models.macro import METRIC_PMI_MFG, METRIC_PMI_NON_MFG, REGION_CN
from astock.sources.cn_macro._common import parse_cn_month, to_float
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.market_overview._common import safe_retry_df

logger = logging.getLogger(__name__)


def fetch_pmi() -> SourceFetchResult:
    """AKShare macro_china_pmi → 制造 / 非制造 PMI 指数。"""
    df = safe_retry_df("macro_china_pmi", ak.macro_china_pmi, logger=logger)
    if df is None or df.empty:
        return SourceFetchResult.failure("东财 PMI：空结果")

    records: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_cn_month(raw.get("月份"))
        if not period:
            continue
        mfg = to_float(raw.get("制造业-指数"))
        non_mfg = to_float(raw.get("非制造业-指数"))
        if mfg is not None:
            records.append(
                {
                    "region": REGION_CN,
                    "period": period,
                    "metric": METRIC_PMI_MFG,
                    "value": round(float(mfg), 4),
                }
            )
        if non_mfg is not None:
            records.append(
                {
                    "region": REGION_CN,
                    "period": period,
                    "metric": METRIC_PMI_NON_MFG,
                    "value": round(float(non_mfg), 4),
                }
            )
    records.sort(key=lambda r: (r["period"], r["metric"]))
    if not records:
        return SourceFetchResult.failure("东财 PMI：无有效数据")
    return SourceFetchResult(records=records, ok=True)
