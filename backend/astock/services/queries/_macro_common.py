"""宏观查询共享：长表行按 period 透视。"""

from __future__ import annotations

from astock.core.types import MacroMetric
from astock.models.macro import MacroValue


def pivot_macro_rows(
    rows: list[MacroValue],
    metrics: tuple[MacroMetric, ...],
) -> dict[str, dict[str, float | None]]:
    """将长表 MacroValue 行按 period 聚合为 metric → value 字典。"""
    by_period: dict[str, dict[str, float | None]] = {}
    empty = {m: None for m in metrics}
    for row in rows:
        bucket = by_period.setdefault(row.period, dict(empty))
        bucket[row.metric] = row.value
    return by_period
