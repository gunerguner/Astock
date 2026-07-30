"""指数点位数据导入（多指数）。"""

from sqlalchemy import func
from sqlmodel import Session, select

from astock.config import POINT_INDEX_CONFIG, point_sync_meta_key
from astock.datasets.indices import fetch_point
from astock.models.point import Point
from astock.services.imports.pipeline import DailyImportSpec, run_multi_daily_import
from astock.services.sync.results import ImportResult


def _index_last_date(db: Session, index_code: str) -> str | None:
    return db.exec(
        select(func.max(Point.date)).where(Point.index_code == index_code)
    ).one()


def import_point(db: Session) -> ImportResult:
    specs: list[DailyImportSpec] = []
    for index_code, config in POINT_INDEX_CONFIG.items():
        index_name = str(config["name"])
        specs.append(
            DailyImportSpec(
                table_name=point_sync_meta_key(index_code),
                model=Point,
                conflict_cols=["date", "index_code"],
                fetch=lambda start, code=index_code: fetch_point(
                    code, start_date=start
                ),
                source_key=index_code,
                failure_message=f"{index_name}点位导入失败",
                log_label=f"{index_name}点位",
                prepare_table="point",
                resolve_last_date=lambda s, code=index_code: _index_last_date(s, code),
                error_label=index_name,
            )
        )
    return run_multi_daily_import(
        db,
        specs,
        aggregate_failure_message="指数点位导入失败",
        log_label="指数点位导入",
        count_model=Point,
    )
