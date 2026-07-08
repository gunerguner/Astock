"""数据导入编排：非流式与 SSE 流式。"""

import logging
from collections.abc import Callable, Iterator

from sqlmodel import Session

from astock.core.progress import ProgressReporter, SSEBridge
from astock.schemas.imports import ImportDataset
from astock.services.imports import (
    import_global_assets,
    import_point,
    import_stock,
    import_turnover,
)
from astock.services.imports._common import aggregate_status
from astock.services.imports.stock_importer import _import_stock_gen

logger = logging.getLogger(__name__)


def import_dataset(
    db: Session,
    dataset: ImportDataset,
    on_progress: ProgressReporter | None = None,
) -> dict:
    def run_phase(key: str, fn: Callable[[Session], dict]) -> dict:
        if on_progress:
            on_progress.phase_start(key)
        result = fn(db)
        if on_progress:
            on_progress.phase_done(key, result)
        return result

    match dataset:
        case ImportDataset.turnover:
            return run_phase("turnover", import_turnover)
        case ImportDataset.point:
            return run_phase("point", import_point)
        case ImportDataset.stock:
            if on_progress:
                on_progress.phase_start("stock")
            result = import_stock(db, on_progress=on_progress)
            if on_progress:
                on_progress.phase_done("stock", result)
            return result
        case ImportDataset.global_assets:
            return run_phase("global_assets", import_global_assets)
        case ImportDataset.all:
            turnover_result = run_phase("turnover", import_turnover)
            point_result = run_phase("point", import_point)
            if on_progress:
                on_progress.phase_start("stock")
            stock_result = import_stock(db, on_progress=on_progress)
            if on_progress:
                on_progress.phase_done("stock", stock_result)
            global_assets_result = run_phase("global_assets", import_global_assets)
            statuses = [
                turnover_result["status"],
                point_result["status"],
                stock_result["status"],
                global_assets_result["status"],
            ]
            return {
                "turnover": turnover_result,
                "point": point_result,
                "stock": stock_result,
                "global_assets": global_assets_result,
                "status": aggregate_status(*statuses),
            }


def _stream_run_phase(
    db: Session,
    key: str,
    fn: Callable[[Session], dict],
    reporter: ProgressReporter,
    bridge: SSEBridge,
) -> Iterator[str]:
    reporter.phase_start(key)
    yield from bridge.drain()
    result = fn(db)
    reporter.phase_done(key, result)
    yield from bridge.drain()
    return result


def _stream_stock_phase(
    db: Session,
    reporter: ProgressReporter,
    bridge: SSEBridge,
) -> Iterator[str]:
    reporter.phase_start("stock")
    yield from bridge.drain()
    stock_gen = _import_stock_gen(db, on_progress=reporter, bridge=bridge)
    try:
        while True:
            yield next(stock_gen)
    except StopIteration as exc:
        stock_result = exc.value
    reporter.phase_done("stock", stock_result)
    yield from bridge.drain()
    return stock_result


def import_dataset_stream(
    db: Session,
    dataset: ImportDataset,
) -> Iterator[str]:
    bridge = SSEBridge()
    reporter = ProgressReporter(bridge.emit)

    try:
        match dataset:
            case ImportDataset.turnover:
                result = yield from _stream_run_phase(
                    db, "turnover", import_turnover, reporter, bridge
                )
            case ImportDataset.point:
                result = yield from _stream_run_phase(
                    db, "point", import_point, reporter, bridge
                )
            case ImportDataset.stock:
                result = yield from _stream_stock_phase(db, reporter, bridge)
            case ImportDataset.global_assets:
                result = yield from _stream_run_phase(
                    db, "global_assets", import_global_assets, reporter, bridge
                )
            case ImportDataset.all:
                turnover_result = yield from _stream_run_phase(
                    db, "turnover", import_turnover, reporter, bridge
                )
                point_result = yield from _stream_run_phase(
                    db, "point", import_point, reporter, bridge
                )
                stock_result = yield from _stream_stock_phase(db, reporter, bridge)
                global_assets_result = yield from _stream_run_phase(
                    db, "global_assets", import_global_assets, reporter, bridge
                )
                result = {
                    "turnover": turnover_result,
                    "point": point_result,
                    "stock": stock_result,
                    "global_assets": global_assets_result,
                    "status": aggregate_status(
                        turnover_result["status"],
                        point_result["status"],
                        stock_result["status"],
                        global_assets_result["status"],
                    ),
                }
            case _:
                raise ValueError(f"unsupported dataset: {dataset}")

        reporter.done(result)
        yield from bridge.drain()
    except Exception as exc:
        logger.exception("流式导入失败")
        reporter.error(str(exc))
        yield from bridge.drain()
