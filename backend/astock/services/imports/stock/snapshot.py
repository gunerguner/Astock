"""个股全市场快照加载（akshare 主路径 + 腾讯回退）。"""

import logging
from collections.abc import Iterator

from astock.core.exceptions import ExternalSourceAppError
from astock.core.progress import ProgressReporter, SSEBridge
from astock.services.imports.stock.context import StockImportContext
from astock.sources.akshare import fetch_stock_spot_snapshot
from astock.sources.baostock import fetch_all_stock_codes
from astock.sources.fetch_result import SourceFetchResult
from astock.sources.tencent import iter_spot_batches

logger = logging.getLogger(__name__)


def drain_bridge(bridge: SSEBridge | None) -> Iterator[str]:
    if bridge is not None:
        yield from bridge.drain()


def report_stock(
    on_progress: ProgressReporter | None,
    detail: str,
    *,
    current: int = 0,
    total: int = 1,
    imported: int = 0,
) -> None:
    if on_progress is not None:
        on_progress.phase_progress(
            "stock", current, total, detail, imported=imported
        )


def load_spot_snapshot(ctx: StockImportContext) -> Iterator[str] | SourceFetchResult:
    """主路径 akshare 一次快照；失败则 baostock 代码池 + 腾讯批量回退。"""
    report_stock(ctx.on_progress, "获取全市场个股快照...")
    yield from drain_bridge(ctx.bridge)

    spot_fr = fetch_stock_spot_snapshot()
    if spot_fr.ok and spot_fr.records:
        return spot_fr

    if not spot_fr.ok:
        logger.warning("akshare 快照失败，回退腾讯: %s", spot_fr.error_summary())

    report_stock(ctx.on_progress, "akshare 失败，回退腾讯行情...")
    yield from drain_bridge(ctx.bridge)

    codes_fr = fetch_all_stock_codes(ctx.as_of_date or "")
    if not codes_fr.ok or not codes_fr.records:
        raise ExternalSourceAppError(
            f"全市场代码清单获取失败: {codes_fr.error_summary()}"
        )

    code_list = [r["code"] for r in codes_fr.records]
    name_by_code = {r["code"]: r["name"] for r in codes_fr.records}

    records: list[dict] = []
    cap_errors: list[str] = []
    for batch_idx, total_batches, batch_records, error in iter_spot_batches(code_list):
        report_stock(
            ctx.on_progress,
            f"腾讯快照 {batch_idx}/{total_batches}",
            current=batch_idx,
            total=total_batches,
        )
        yield from drain_bridge(ctx.bridge)
        if error:
            cap_errors.append(error)
            continue
        for row in batch_records:
            code = row["code"]
            if not row.get("name"):
                row["name"] = name_by_code.get(code, "")
            records.append(row)

    if not records:
        detail = "; ".join((spot_fr.errors + cap_errors)[:3]) or "无有效记录"
        raise ExternalSourceAppError(f"股票快照失败(akshare+腾讯): {detail}")
    if cap_errors:
        logger.warning(
            "腾讯快照部分批次失败(%s)，已用 %s 条继续: %s",
            len(cap_errors),
            len(records),
            "; ".join(cap_errors[:3]),
        )

    return SourceFetchResult(records=records, ok=True)
