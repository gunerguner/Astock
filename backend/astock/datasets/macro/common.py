"""宏观数据集共享：长表记录构造、子源合并与主备源回退。"""


import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from astock.core.datetime_utils import today_local_date
from astock.datasets.macro.types import MacroMetric, MacroRegion
from astock.datasets.result import FetchResult
from astock.providers._shared.parsing import parse_cn_month, to_float

logger = logging.getLogger(__name__)

__all__ = [
    "macro_record",
    "merge_domain_sources",
    "months_behind",
    "parse_cn_month",
    "records_from_month_df",
    "to_float",
    "with_fallback",
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


def months_behind(period: str, today: date | None = None) -> int | None:
    """YYYY-MM 相对 today（默认上海今日）滞后的整月数；解析失败返回 None。"""
    now = today or today_local_date()
    try:
        year, month = int(period[:4]), int(period[5:7])
        return (now.year - year) * 12 + (now.month - month)
    except (TypeError, ValueError, IndexError):
        return None


def with_fallback(
    primary: FetchResult,
    fallback_fn: Callable[[], FetchResult],
    *,
    max_lag_months: int,
    label: str,
    fallback_error_label: str,
) -> FetchResult:
    """主源成功且最新 period 滞后 ≤ max_lag_months 时直接返回，否则回退备源。"""
    lag_ok = False
    if primary.ok and primary.records:
        lag = months_behind(str(primary.records[-1]["period"]))
        lag_ok = lag is not None and 0 <= lag <= max_lag_months

    if primary.ok and primary.records and lag_ok:
        return primary

    logger.warning(
        "%s主源不可用或滞后，回退备源 (ok=%s records=%s lag_ok=%s errors=%s)",
        label,
        primary.ok,
        len(primary.records),
        lag_ok,
        primary.errors,
    )
    fallback = fallback_fn()
    if fallback.ok and fallback.records:
        if not primary.ok:
            logger.info(
                "%s使用备源（主源错误: %s）",
                label,
                primary.error_summary(),
            )
        return fallback
    if primary.records:
        primary.ok = False
        primary.errors.append(fallback.error_summary() or fallback_error_label)
        return primary
    return FetchResult.failure(
        "; ".join(
            filter(
                None,
                [
                    primary.error_summary(),
                    fallback.error_summary(),
                    f"{label}主备源均失败",
                ],
            )
        )
    )
