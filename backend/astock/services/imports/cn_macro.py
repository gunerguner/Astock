"""中国宏观数据导入（月频 + sync_meta，写入统一 macro_value 长表）。"""


from sqlmodel import Session

from astock.config import CN_MACRO_REFRESH_DAY
from astock.datasets.macro import fetch_cn_macro
from astock.datasets.macro.types import MacroMetric
from astock.services.imports._macro_domain import run_macro_import
from astock.services.sync.results import ImportResult

_SYNC_TABLE = "cn_macro"
_CN_METRICS: tuple[MacroMetric, ...] = (
    "cpi_yoy",
    "ppi_yoy",
    "pmi_manufacturing",
    "pmi_non_manufacturing",
    "consumer_confidence",
)


def import_cn_macro(db: Session) -> ImportResult:
    """拉取中国宏观月度指标并 upsert；尊重月频跳过窗口。"""
    return run_macro_import(
        db,
        region="cn",
        sync_table=_SYNC_TABLE,
        refresh_day=CN_MACRO_REFRESH_DAY,
        fetch_fn=fetch_cn_macro,
        log_label="中国宏观",
        required_metrics=_CN_METRICS,
    )
