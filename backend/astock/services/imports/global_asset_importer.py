"""全球资产数据导入。"""

import logging
import time

from sqlmodel import Session

from astock.services.global_asset.refresh import refresh_asset_highs

logger = logging.getLogger(__name__)


def import_global_assets(db: Session) -> dict:
    start_ts = time.perf_counter()
    result = refresh_asset_highs(db)
    elapsed = time.perf_counter() - start_ts
    result["elapsed"] = round(elapsed, 2)
    logger.info(
        "全球资产最高点刷新完成: imported=%s total=%s status=%s elapsed=%.2fs",
        result["imported"],
        result["total"],
        result["status"],
        elapsed,
    )
    return result
