import logging
from pathlib import Path

from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine

from astock.config import DATABASE_URL, DB_PATH
import astock.models  # noqa: F401

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def get_db():
    with Session(engine) as session:
        yield session


def _apply_schema_migrations() -> None:
    """幂等轻量迁移。新列只在此追加步骤，不引入 Alembic。"""
    steps: list[tuple[str, str]] = [
        ("20261019_baseline", "SELECT 1"),
    ]
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)"
        )
        applied = {
            row[0]
            for row in conn.exec_driver_sql("SELECT version FROM schema_migrations")
        }
        for version, sql in steps:
            if version in applied:
                continue
            conn.exec_driver_sql(sql)
            conn.exec_driver_sql(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
            logger.info("已应用 schema 迁移 %s", version)


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _apply_schema_migrations()
    logger.info("数据库表结构同步完成")
