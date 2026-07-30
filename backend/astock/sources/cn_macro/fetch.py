"""拼接中国宏观各子源成功记录（长表，不补空字段）。"""

from __future__ import annotations

import logging

from astock.sources.cn_macro.consumer import fetch_consumer_confidence
from astock.sources.cn_macro.cpi import fetch_cpi, fetch_ppi
from astock.sources.cn_macro.pmi import fetch_pmi
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def fetch_cn_macro() -> SourceFetchResult:
    """串行拉取中国宏观月度指标；仅拼接成功返回的长表记录。"""
    sources = (
        ("CPI", fetch_cpi()),
        ("PPI", fetch_ppi()),
        ("PMI", fetch_pmi()),
        ("消费者信心", fetch_consumer_confidence()),
    )

    records = []
    errors: list[str] = []
    for label, src in sources:
        errors.extend(src.errors)
        if src.ok and src.records:
            records.extend(src.records)
        else:
            errors.append(src.error_summary() or f"{label} 拉取不完整")

    if not records:
        msg = "; ".join(errors) if errors else "中国宏观：无数据"
        return SourceFetchResult.failure(msg)

    ok = all(src.ok and bool(src.records) for _, src in sources)
    result = SourceFetchResult(records=records, ok=ok, errors=errors)
    logger.info(
        "中国宏观拉取完成: records=%s ok=%s sources=%s",
        len(result.records),
        result.ok,
        {label: src.ok for label, src in sources},
    )
    return result
