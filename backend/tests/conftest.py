"""pytest 共享夹具：内存 SQLite + TestClient + Redis 内存 stub。

约束：必须在 import astock.* 之前设置 DB_PATH / LOG_DIR ——
astock.config 在 import 时固化这些常量，astock.core.database 据此
创建模块级 engine 单例。业务 session 一律经 dependency_overrides
注入内存库，不触碰 backend/db/astock.db。
"""

import importlib
import json
import os
import tempfile
from collections.abc import Iterator

_TMP_DIR = tempfile.mkdtemp(prefix="astock-pytest-")
os.environ.setdefault("DB_PATH", os.path.join(_TMP_DIR, "astock-test.db"))
os.environ.setdefault("LOG_DIR", os.path.join(_TMP_DIR, "logs"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from astock.core.database import get_db
from astock.core.sync_status import SyncStatus
from astock.main import app

# 不进入 with 上下文：避免触发 lifespan（init_db 会写 DB_PATH 指向的
# 文件库）。HTTP 请求所需的 session 全部来自 dependency_overrides。
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_test_engine)

_CACHED_AT = "2026-01-01T00:00:00+00:00"


class FakeRedisGateway:
    """内存版 RedisGateway，方法签名与生产实现对齐（ttl 仅接受并忽略）。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get_string(self, key: str) -> str | None:
        return self.store.get(key)

    def set_string(self, key: str, value: str, *, ttl: int | None = None) -> bool:
        self.store[key] = value
        return True

    def delete_key(self, key: str) -> bool:
        return self.store.pop(key, None) is not None

    def get_json(self, key: str) -> object | None:
        raw = self.store.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: object, *, ttl: int | None = None) -> bool:
        return self.set_string(key, json.dumps(value, ensure_ascii=False), ttl=ttl)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedisGateway:
    """替换 redis_gateway 的全部使用点。

    各模块 `from astock.core.redis_client import redis_gateway` 是绑定
    引用，必须逐使用方模块 patch，不能只 patch 定义处。
    """
    gateway = FakeRedisGateway()
    for module_name in (
        "astock.services.cache.asset_prices",
        "astock.services.cache.closes",
        "astock.services.queries.global_asset",
        "astock.services.queries.market_overview.service",
    ):
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "redis_gateway", gateway)
    return gateway


@pytest.fixture
def db_session() -> Iterator[Session]:
    with Session(_test_engine) as session:
        yield session
    # StaticPool 内存库跨测试共享连接,测试后清空全部表避免状态泄漏
    with Session(_test_engine) as session:
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class SeedFactory:
    """按模型字段最小化落库的种子工厂（显式 commit）。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def point(self, date: str, index_code: str, close: float) -> None:
        from astock.models.point import Point

        self.db.add(Point(date=date, index_code=index_code, close=close, cached_at=_CACHED_AT))
        self.db.commit()

    def points(self, rows: list[tuple[str, str, float]]) -> None:
        from astock.models.point import Point

        self.db.add_all(
            Point(date=d, index_code=code, close=close, cached_at=_CACHED_AT)
            for d, code, close in rows
        )
        self.db.commit()

    def turnover(self, date: str, sse: float, szse: float) -> None:
        from astock.models.turnover import Turnover

        self.db.add(
            Turnover(
                date=date, sse_amount=sse, szse_amount=szse, turnover=sse + szse,
                cached_at=_CACHED_AT,
            )
        )
        self.db.commit()

    def turnovers(self, rows: list[tuple[str, float, float]]) -> None:
        for d, sse, szse in rows:
            self.turnover(d, sse, szse)

    def stock_turnover(self, date: str, code: str, name: str, amount: float) -> None:
        from astock.models.stock_turnover import StockTurnover

        self.db.add(
            StockTurnover(date=date, code=code, name=name, amount=amount, cached_at=_CACHED_AT)
        )
        self.db.commit()

    def macro(self, region: str, period: str, metric: str, value: float) -> None:
        from astock.models.macro import MacroValue

        self.db.add(
            MacroValue(region=region, period=period, metric=metric, value=value, cached_at=_CACHED_AT)
        )
        self.db.commit()

    def asset_high(
        self, ticker: str, name: str, asset_type: str, all_time_high: float, ath_date: str
    ) -> None:
        from astock.models.asset_high import AssetHigh

        self.db.add(
            AssetHigh(
                ticker=ticker, name=name, asset_type=asset_type,
                all_time_high=all_time_high, ath_date=ath_date, cached_at=_CACHED_AT,
            )
        )
        self.db.commit()

    def sync_meta(
        self,
        table_name: str,
        last_synced_date: str,
        status: SyncStatus = SyncStatus.SUCCESS,
        last_synced_at: str = _CACHED_AT,
    ) -> None:
        from astock.models.sync_meta import SyncMeta

        self.db.add(
            SyncMeta(
                table_name=table_name, last_synced_date=last_synced_date,
                last_synced_at=last_synced_at, last_status=status,
            )
        )
        self.db.commit()


@pytest.fixture
def seed(db_session: Session) -> SeedFactory:
    return SeedFactory(db_session)
