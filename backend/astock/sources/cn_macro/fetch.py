"""拼接中国宏观各子源成功记录（长表，不补空字段）。"""

from __future__ import annotations

from astock.sources._macro_common import merge_domain_sources
from astock.sources.cn_macro.consumer import fetch_consumer_confidence
from astock.sources.cn_macro.cpi import fetch_cpi, fetch_ppi
from astock.sources.cn_macro.pmi import fetch_pmi
from astock.sources.fetch_result import SourceFetchResult


def fetch_cn_macro() -> SourceFetchResult:
    """串行拉取中国宏观月度指标；仅拼接成功返回的长表记录。"""
    return merge_domain_sources(
        "中国宏观",
        [
            ("CPI", fetch_cpi()),
            ("PPI", fetch_ppi()),
            ("PMI", fetch_pmi()),
            ("消费者信心", fetch_consumer_confidence()),
        ],
    )
