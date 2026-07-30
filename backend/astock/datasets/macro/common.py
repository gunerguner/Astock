"""宏观数据集共享：长表记录构造与子源合并。"""

from __future__ import annotations

import logging
from typing import Any

from astock.core.types import MacroMetric, MacroRegion
from astock.datasets.result import FetchResult
from astock.providers._shared.parsing import parse_cn_month, to_float

logger = logging.getLogger(__name__)

__all__ = [
    "macro_record",
    "merge_domain_sources",
    "parse_cn_month",
    "records_from_month_df",
    "to_float",
]


def macro_record(
    *,
    region: MacroRegion,
    period: str,
    metric: MacroMetric,
    value: float,
) -> dict[str, Any]:
    return {
        "region": region,
        "period": period,
        "metric": metric,
        "value": round(float(value), 4),
    }


def records_from_month_df(
    df: Any,
    *,
    region: MacroRegion,
    month_col: str,
    value_specs: list[tuple[str, MacroMetric]],
    parse_month=parse_cn_month,
) -> list[dict[str, Any]]:
    """从月度宽表提取长表记录。

    value_specs: [(column_name, metric_code), ...]
    """
    out: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_month(raw.get(month_col))
        if not period:
            continue
        for col, metric in value_specs:
            value = to_float(raw.get(col))
            if value is None:
                continue
            out.append(macro_record(region=region, period=period, metric=metric, value=value))
    out.sort(key=lambda r: (r["period"], r["metric"]))
    return out


def merge_domain_sources(
    domain_label: str,
    sources: list[tuple[str, FetchResult]],
) -> FetchResult:
    """串行子源结果拼接为长表记录；仅保留成功源，失败记入 errors。"""
    records = []
    errors: list[str] = []
    for label, src in sources:
        errors.extend(src.errors)
        if src.ok and src.records:
            records.extend(src.records)
        else:
            errors.append(src.error_summary() or f"{label} 拉取不完整")

    if not records:
        msg = "; ".join(errors) if errors else f"{domain_label}：无数据"
        return FetchResult.failure(msg)

    ok = all(src.ok and bool(src.records) for _, src in sources)
    result = FetchResult(records=records, ok=ok, errors=errors)
    logger.info(
        "%s拉取完成: records=%s ok=%s sources=%s",
        domain_label,
        len(result.records),
        result.ok,
        {label: src.ok for label, src in sources},
    )
    return result
