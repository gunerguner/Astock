"""中国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""

from __future__ import annotations

from sqlmodel import Session

from astock.config import CN_MACRO_REFRESH_DAY
from astock.datasets.macro import fetch_cn_macro
from astock.services.imports._macro_domain import run_macro_import
from astock.services.sync.results import ImportResult

_SYNC_TABLE = "cn_macro"


def import_cn_macro(db: Session) -> ImportResult:
    """拉取中国宏观月度指标并 upsert；尊重月频跳过窗口。"""
    return run_macro_import(
        db,
        region="cn",
        sync_table=_SYNC_TABLE,
        refresh_day=CN_MACRO_REFRESH_DAY,
        fetch_fn=fetch_cn_macro,
        log_label="中国宏观",
    )
