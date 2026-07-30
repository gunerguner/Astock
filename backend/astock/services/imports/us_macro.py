"""美国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlmodel import Session

from astock.config import US_MACRO_REFRESH_DAY
from astock.models.macro import REGION_US
from astock.services.imports._macro_domain import (
    expected_macro_period,
    run_macro_import,
    should_skip_macro,
)
from astock.sources.us_macro import fetch_us_macro

_SYNC_TABLE = "us_macro"


def expected_us_macro_period(
    today: date | None = None,
    *,
    refresh_day: int = US_MACRO_REFRESH_DAY,
) -> str:
    """北京时间下当前应覆盖的最新 CPI 月份。"""
    return expected_macro_period(today, refresh_day=refresh_day)


def should_skip_us_macro(
    db: Session,
    *,
    refresh_day: int = US_MACRO_REFRESH_DAY,
) -> bool:
    """水位已覆盖期望月份且上次成功、该 region 有数据时跳过外网。"""
    return should_skip_macro(
        db,
        region=REGION_US,
        sync_table=_SYNC_TABLE,
        refresh_day=refresh_day,
    )


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
