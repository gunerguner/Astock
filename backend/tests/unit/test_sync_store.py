"""sync/store:batch_upsert 语义、水位推进与跳过判定。"""

import pytest

from astock.config import START_DATE
from astock.core.datetime_utils import add_calendar_days
from astock.core.sync_status import SyncStatus
from astock.models.macro import MacroValue
from astock.models.point import Point
from astock.models.sync_meta import SyncMeta
from astock.services.sync.store import (
    batch_upsert,
    count_macro_rows,
    count_rows,
    get_last_date,
    get_sync_meta,
    get_sync_start_date,
    should_skip_daily_sync,
    upsert_sync_meta,
)


def test_batch_upsert_inserts_new_rows(db_session):
    total = batch_upsert(
        db_session,
        Point,
        [
            {"date": "2026-09-29", "index_code": "000001", "close": 3900.0, "cached_at": "t"},
            {"date": "2026-09-30", "index_code": "000001", "close": 3950.0, "cached_at": "t"},
        ],
        ["date", "index_code"],
    )
    assert total == 2
    assert count_rows(db_session, Point) == 2


def test_batch_upsert_conflict_updates_non_key_columns(db_session):
    rows = [
        {"date": "2026-09-30", "index_code": "000001", "close": 3900.0, "cached_at": "t1"},
        {"date": "2026-09-30", "index_code": "000001", "close": 3950.0, "cached_at": "t2"},
    ]
    batch_upsert(db_session, Point, rows, ["date", "index_code"])
    batch_upsert(db_session, Point, rows[1:], ["date", "index_code"])

    assert count_rows(db_session, Point) == 1
    row = db_session.get(Point, ("2026-09-30", "000001"))
    assert row.close == 3950.0
    assert row.cached_at == "t2"


def test_batch_upsert_splits_batches(db_session):
    records = [
        {"period": f"2026-{m:02d}", "region": "us", "metric": "cpi_yoy", "value": float(m), "cached_at": "t"}
        for m in range(1, 6)
    ]
    total = batch_upsert(db_session, MacroValue, records, ["region", "period", "metric"], batch_size=2)
    assert total == 5
    assert count_macro_rows(db_session, "us") == 5


def test_batch_upsert_empty_records_is_noop(db_session):
    assert batch_upsert(db_session, Point, [], ["date", "index_code"]) == 0


def test_upsert_sync_meta_creates_then_updates(db_session):
    synced_at = upsert_sync_meta(
        db_session, "turnover", last_synced_date="2026-10-04", status=SyncStatus.SUCCESS
    )
    assert synced_at
    meta = get_sync_meta(db_session, "turnover")
    assert meta.last_synced_date == "2026-10-04"
    assert meta.last_status == SyncStatus.SUCCESS

    upsert_sync_meta(
        db_session, "turnover", last_synced_date="2026-10-05", status=SyncStatus.PARTIAL_FAILURE
    )
    meta = get_sync_meta(db_session, "turnover")
    assert meta.last_synced_date == "2026-10-05"
    assert meta.last_status == SyncStatus.PARTIAL_FAILURE
    assert count_rows(db_session, SyncMeta) == 1


def test_get_last_date(db_session):
    assert get_last_date(db_session, Point) is None
    batch_upsert(
        db_session,
        Point,
        [
            {"date": "2026-09-29", "index_code": "000001", "close": 1.0, "cached_at": "t"},
            {"date": "2026-09-30", "index_code": "000001", "close": 2.0, "cached_at": "t"},
        ],
        ["date", "index_code"],
    )
    assert get_last_date(db_session, Point) == "2026-09-30"


def test_get_sync_start_date_defaults_to_start_date(db_session):
    assert get_sync_start_date(db_session, "turnover") == START_DATE
    upsert_sync_meta(db_session, "turnover", last_synced_date="2026-10-04", status=SyncStatus.SUCCESS)
    # 增量起点 = 上次已同步日的次日
    assert get_sync_start_date(db_session, "turnover") == add_calendar_days("2026-10-04", 1)


def test_should_skip_daily_sync_requires_success_and_coverage(db_session):
    # 无水位:不跳过
    assert should_skip_daily_sync(db_session, "turnover") is False

    # 水位在遥远过去(START_DATE 附近),永远未覆盖最近结算日:不跳过
    upsert_sync_meta(db_session, "turnover", last_synced_date="2005-01-01", status=SyncStatus.SUCCESS)
    assert should_skip_daily_sync(db_session, "turnover") is False

    # 非 SUCCESS 状态:不跳过
    upsert_sync_meta(db_session, "turnover", last_synced_date="2099-12-31", status=SyncStatus.PARTIAL_FAILURE)
    assert should_skip_daily_sync(db_session, "turnover") is False

    # SUCCESS 且水位覆盖最近可结算日:跳过(用未来日期保证与当前时钟无关)
    upsert_sync_meta(db_session, "turnover", last_synced_date="2099-12-31", status=SyncStatus.SUCCESS)
    assert should_skip_daily_sync(db_session, "turnover") is True
