"""成交额数据导入。"""

from sqlmodel import Session

from astock.models.turnover import Turnover
from astock.services.imports.pipeline import run_daily_import
from astock.sources.baostock import fetch_turnover


def import_turnover(db: Session) -> dict:
    return run_daily_import(
        db,
        table_name="turnover",
        model=Turnover,
        conflict_cols=["date"],
        fetch=fetch_turnover,
        source_key="turnover",
        failure_message="成交额导入失败",
        log_label="成交额",
    )
