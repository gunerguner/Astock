"""中国/美国宏观公开入口。"""


from astock.datasets.macro.china import (
    fetch_consumer_confidence,
    fetch_cpi as fetch_cn_cpi,
    fetch_pmi,
    fetch_ppi,
)
from astock.datasets.macro.common import merge_domain_sources
from astock.datasets.macro.us_cpi import fetch_cpi as fetch_us_cpi
from astock.datasets.macro.us_rates import fetch_fed_rate
from astock.datasets.result import FetchResult


def fetch_cn_macro() -> FetchResult:
    """串行拉取中国宏观月度指标；仅拼接成功返回的长表记录。"""
    return merge_domain_sources(
        "中国宏观",
        [
            ("CPI", fetch_cn_cpi()),
            ("PPI", fetch_ppi()),
            ("PMI", fetch_pmi()),
            ("消费者信心", fetch_consumer_confidence()),
        ],
    )


def fetch_us_macro() -> FetchResult:
    """串行拉取美国宏观月度指标；仅拼接成功返回的长表记录。"""
    return merge_domain_sources(
        "美国宏观",
        [
            ("CPI", fetch_us_cpi()),
            ("Fed 利率", fetch_fed_rate()),
        ],
    )
