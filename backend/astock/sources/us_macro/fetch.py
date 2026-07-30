"""拼接美国宏观各子源成功记录（长表，不补空字段）。"""

from __future__ import annotations

from astock.sources._macro_common import merge_domain_sources
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.us_macro.cpi import fetch_cpi
from astock.sources.us_macro.fed_rate import fetch_fed_rate


def fetch_us_macro() -> SourceFetchResult:
    """串行拉取美国宏观月度指标；仅拼接成功返回的长表记录。"""
    return merge_domain_sources(
        "美国宏观",
        [
            ("CPI", fetch_cpi()),
            ("Fed 利率", fetch_fed_rate()),
        ],
    )
