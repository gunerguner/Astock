"""指数点位数据导入（多指数）。"""

from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import POINT_INDEX_CONFIG, point_sync_meta_key
from astock.models.point import Point
from astock.services.imports.pipeline import run_multi_daily_import
from astock.sources.akshare import fetch_cn_index_point
from astock.sources.baostock import fetch_point
from astock.sources.fetch_result import SourceFetchResult


def _fetch_point_index(index_code: str, start_date: str) -> SourceFetchResult:
    config = POINT_INDEX_CONFIG[index_code]
    source = str(config.get("source", "baostock"))
    if source == "akshare":
        return fetch_cn_index_point(index_code, start_date=start_date)
    return fetch_point(index_code=index_code, start_date=start_date)


def _index_last_date(db: Session, index_code: str) -> str | None:
    return db.exec(
        select(func.max(Point.date)).where(Point.index_code == index_code)
    ).one()


def import_point(db: Session) -> dict:
    items = []
    for index_code, config in POINT_INDEX_CONFIG.items():
        index_name = str(config["name"])
        items.append(
            {
                "table_name": point_sync_meta_key(index_code),
                "model": Point,
                "conflict_cols": ["date", "index_code"],
                "fetch": lambda start, code=index_code: _fetch_point_index(code, start),
                "source_key": index_code,
                "failure_message": f"{index_name}点位导入失败",
                "log_label": f"{index_name}点位",
                "prepare_table": "point",
                "resolve_last_date": lambda s, code=index_code: _index_last_date(s, code),
                "error_label": index_name,
            }
        )
    return run_multi_daily_import(
        db,
        items,
        aggregate_failure_message="指数点位导入失败",
        log_label="指数点位导入",
        count_model=Point,
    )
