"""宏观领域共享：拼接多子源成功记录。"""

from __future__ import annotations

import logging

from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)


def merge_domain_sources(
    domain_label: str,
    sources: list[tuple[str, SourceFetchResult]],
) -> SourceFetchResult:
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
        return SourceFetchResult.failure(msg)

    ok = all(src.ok and bool(src.records) for _, src in sources)
    result = SourceFetchResult(records=records, ok=ok, errors=errors)
    logger.info(
        "%s拉取完成: records=%s ok=%s sources=%s",
        domain_label,
        len(result.records),
        result.ok,
        {label: src.ok for label, src in sources},
    )
    return result
