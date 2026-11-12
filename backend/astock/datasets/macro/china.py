"""中国宏观月度指标：CPI/PPI/PMI/消费者信心。"""

from collections.abc import Callable
from typing import Any

from astock.datasets.macro.common import records_from_month_df
from astock.datasets.macro.types import MacroMetric
from astock.datasets.result import FetchResult
from astock.providers.akshare import economics as ak_econ


def _fetch_monthly(
    fetch_fn: Callable[[], Any],
    label: str,
    value_specs: list[tuple[str, MacroMetric]],
    *,
    invalid: str,
) -> FetchResult:
    df = fetch_fn()
    if df is None or df.empty:
        return FetchResult.failure(f"东财 {label}：空结果")
    records = records_from_month_df(
        df,
        region="cn",
        month_col="月份",
        value_specs=value_specs,
    )
    if not records:
        return FetchResult.failure(f"东财 {label}：{invalid}")
    return FetchResult(records=records, ok=True)


def fetch_cpi() -> FetchResult:
    return _fetch_monthly(
        ak_econ.fetch_china_cpi, "CPI", [("全国-同比增长", "cpi_yoy")], invalid="无有效同比数据"
    )


def fetch_ppi() -> FetchResult:
    return _fetch_monthly(
        ak_econ.fetch_china_ppi, "PPI", [("当月同比增长", "ppi_yoy")], invalid="无有效同比数据"
    )


def fetch_pmi() -> FetchResult:
    return _fetch_monthly(
        ak_econ.fetch_china_pmi,
        "PMI",
        [("制造业-指数", "pmi_manufacturing"), ("非制造业-指数", "pmi_non_manufacturing")],
        invalid="无有效数据",
    )


def fetch_consumer_confidence() -> FetchResult:
    return _fetch_monthly(
        ak_econ.fetch_china_consumer_confidence,
        "消费者信心",
        [("消费者信心指数-指数值", "consumer_confidence")],
        invalid="无有效数据",
    )
