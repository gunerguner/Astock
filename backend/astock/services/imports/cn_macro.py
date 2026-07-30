"""中国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlmodel import Session

from astock.config import CN_MACRO_REFRESH_DAY
from astock.models.macro import REGION_CN
from astock.services.imports._macro_domain import (
    expected_macro_period,
    run_macro_import,
    should_skip_macro,
)
from astock.sources.cn_macro import fetch_cn_macro

_SYNC_TABLE = "cn_macro"


def expected_cn_macro_period(
    today: date | None = None,
    *,
    refresh_day: int = CN_MACRO_REFRESH_DAY,
) -> str:
    """北京时间下当前应覆盖的最新宏观月份。"""
    return expected_macro_period(today, refresh_day=refresh_day)


def should_skip_cn_macro(
    db: Session,
    *,
    refresh_day: int = CN_MACRO_REFRESH_DAY,
) -> bool:
    """水位已覆盖期望月份且上次成功、该 region 有数据时跳过外网。"""
    return should_skip_macro(
        db,
        region=REGION_CN,
        sync_table=_SYNC_TABLE,
        refresh_day=refresh_day,
    )


def import_cn_macro(db: Session) -> dict[str, Any]:
    """拉取中国宏观月度指标并 upsert；尊重月频跳过窗口。"""
    return run_macro_import(
        db,
        region=REGION_CN,
        sync_table=_SYNC_TABLE,
        refresh_day=CN_MACRO_REFRESH_DAY,
        fetch_fn=fetch_cn_macro,
        log_label="中国宏观",
    )
