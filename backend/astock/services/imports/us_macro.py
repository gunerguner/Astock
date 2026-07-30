"""美国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from astock.config import US_MACRO_REFRESH_DAY
from astock.datasets.macro import fetch_us_macro
from astock.models.macro import REGION_US
from astock.services.imports._macro_domain import run_macro_import

_SYNC_TABLE = "us_macro"


def import_us_macro(db: Session) -> dict[str, Any]:
    """拉取美国宏观月度指标并 upsert；尊重月频跳过窗口。"""
    return run_macro_import(
        db,
        region=REGION_US,
        sync_table=_SYNC_TABLE,
        refresh_day=US_MACRO_REFRESH_DAY,
        fetch_fn=fetch_us_macro,
        log_label="美国宏观",
    )
