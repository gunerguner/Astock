"""中国宏观月度指标：CPI/PPI/PMI/消费者信心。"""

from __future__ import annotations

from astock.datasets.macro.common import records_from_month_df
from astock.datasets.result import FetchResult
from astock.providers.akshare import economics as ak_econ


def fetch_cpi() -> FetchResult:
    df = ak_econ.fetch_china_cpi()
    if df is None or df.empty:
        return FetchResult.failure("东财 CPI：空结果")
    records = records_from_month_df(
        df,
        region="cn",
        month_col="月份",
        value_specs=[("全国-同比增长", "cpi_yoy")],
    )
    if not records:
        return FetchResult.failure("东财 CPI：无有效同比数据")
    return FetchResult(records=records, ok=True)


def fetch_ppi() -> FetchResult:
    df = ak_econ.fetch_china_ppi()
    if df is None or df.empty:
        return FetchResult.failure("东财 PPI：空结果")
    records = records_from_month_df(
        df,
        region="cn",
        month_col="月份",
        value_specs=[("当月同比增长", "ppi_yoy")],
    )
    if not records:
        return FetchResult.failure("东财 PPI：无有效同比数据")
    return FetchResult(records=records, ok=True)


def fetch_pmi() -> FetchResult:
    df = ak_econ.fetch_china_pmi()
    if df is None or df.empty:
        return FetchResult.failure("东财 PMI：空结果")
    records = records_from_month_df(
        df,
        region="cn",
        month_col="月份",
        value_specs=[
            ("制造业-指数", "pmi_manufacturing"),
            ("非制造业-指数", "pmi_non_manufacturing"),
        ],
    )
    if not records:
        return FetchResult.failure("东财 PMI：无有效数据")
    return FetchResult(records=records, ok=True)


def fetch_consumer_confidence() -> FetchResult:
    df = ak_econ.fetch_china_consumer_confidence()
    if df is None or df.empty:
        return FetchResult.failure("东财消费者信心：空结果")
    records = records_from_month_df(
        df,
        region="cn",
        month_col="月份",
        value_specs=[("消费者信心指数-指数值", "consumer_confidence")],
    )
    if not records:
        return FetchResult.failure("东财消费者信心：无有效数据")
    return FetchResult(records=records, ok=True)
