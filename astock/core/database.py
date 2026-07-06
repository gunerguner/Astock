import logging
from pathlib import Path

from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine

from astock.config import DATABASE_URL, DB_PATH

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


def init_db():
    import astock.models  # noqa: F401

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    logger.info("数据库表结构同步完成")
