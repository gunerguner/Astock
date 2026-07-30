"""合并 CPI 与联邦基金利率为月度宏观记录。"""

from __future__ import annotations

import logging
from typing import Any

from astock.sources.fetch_result import SourceFetchResult
from astock.sources.us_macro.cpi import fetch_cpi
from astock.sources.us_macro.fed_rate import fetch_fed_rate

logger = logging.getLogger(__name__)


def _index_by_period(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["period"]): r for r in records if r.get("period")}


def merge_us_macro(
    cpi: SourceFetchResult,
    fed: SourceFetchResult,
) -> SourceFetchResult:
    """以 CPI 已发布月份为主轴，对齐同月联邦基金利率上限。"""
    errors: list[str] = []
    errors.extend(cpi.errors)
    errors.extend(fed.errors)

    if not cpi.records and not fed.records:
        msg = "; ".join(errors) if errors else "美国宏观：无数据"
        return SourceFetchResult.failure(msg)

    cpi_map = _index_by_period(cpi.records)
    fed_map = _index_by_period(fed.records)

    # 主轴：有 CPI 的月份；若仅有利率也保留（少见）
    periods = sorted(set(cpi_map) | set(fed_map))
    merged: list[dict[str, Any]] = []
    for period in periods:
        c = cpi_map.get(period, {})
        f = fed_map.get(period, {})
        # 仅利率、无 CPI 的月份：若该月晚于最新 CPI，丢弃（避免未来月份）
        if not c and cpi_map:
            max_cpi = max(cpi_map)
            if period > max_cpi:
                continue
        merged.append(
            {
                "period": period,
                "cpi_yoy": c.get("cpi_yoy"),
                "fed_rate_upper": f.get("fed_rate_upper"),
            }
        )

    ok = cpi.ok and fed.ok and bool(merged)
    if not merged:
        return SourceFetchResult(records=[], ok=False, errors=errors or ["合并后无记录"])
    # 至少一侧成功且有记录 → 可入库；另一侧失败记入 errors
    if (cpi.records or fed.records) and merged:
        ok = bool(cpi.records) and bool(fed.records) and cpi.ok and fed.ok
        if not cpi.ok:
            errors.append(cpi.error_summary() or "CPI 拉取不完整")
        if not fed.ok:
            errors.append(fed.error_summary() or "Fed 利率拉取不完整")
    return SourceFetchResult(records=merged, ok=ok, errors=errors)


def fetch_us_macro() -> SourceFetchResult:
    """拉取并合并美国宏观月度序列。"""
    cpi = fetch_cpi()
    fed = fetch_fed_rate()
    result = merge_us_macro(cpi, fed)
    logger.info(
        "美国宏观拉取完成: records=%s ok=%s cpi_ok=%s fed_ok=%s",
        len(result.records),
        result.ok,
        cpi.ok,
        fed.ok,
    )
    return result
