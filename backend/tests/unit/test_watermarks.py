"""水位、成交额残缺行、宏观跳过与价格覆盖的回归。"""

from contextlib import contextmanager

import pandas as pd
import pytest

from astock.core.price_utils import closes_cover_settled
from astock.core.sync_status import SyncStatus
from astock.datasets.result import FetchResult
from astock.models.point import Point
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.imports.pipeline import DailyImportSpec, run_daily_import
from astock.services.imports.progress import ProgressReporter, SSEBridge
from astock.services.sync.store import get_sync_meta, upsert_sync_meta


def _drain(gen):
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def test_turnover_one_sided_failure_does_not_zero_fill(monkeypatch):
    import astock.datasets.turnover as mod
    from astock.providers.baostock.client import BaostockQueryError

    monkeypatch.setattr(mod, "last_settled_date", lambda market="cn": "2026-01-08")

    @contextmanager
    def session():
        yield object()

    monkeypatch.setattr(mod, "baostock_session", session)
    monkeypatch.setattr(mod, "login_error", lambda _lg: None)

    def query(code, **_kwargs):
        if str(code).startswith("sh"):
            raise BaostockQueryError("上证失败")
        return pd.DataFrame({"date": ["2026-01-08"], "szse_amount": [10.0]})

    monkeypatch.setattr(mod.bs_market, "query_exchange_amount", query)
    fr = mod.fetch_turnover("2026-01-08")
    assert fr.ok is False
    assert fr.records == []


def test_turnover_silent_empty_side_is_not_success(monkeypatch):
    import astock.datasets.turnover as mod

    monkeypatch.setattr(mod, "last_settled_date", lambda market="cn": "2026-01-08")

    @contextmanager
    def session():
        yield object()

    monkeypatch.setattr(mod, "baostock_session", session)
    monkeypatch.setattr(mod, "login_error", lambda _lg: None)

    def query(code, **_kwargs):
        if str(code).startswith("sh"):
            return pd.DataFrame({"date": ["2026-01-08"], "sse_amount": [10.0]})
        return None

    monkeypatch.setattr(mod.bs_market, "query_exchange_amount", query)
    fr = mod.fetch_turnover("2026-01-08")
    assert fr.ok is False
    assert fr.records == []
    assert any("为空" in err for err in fr.errors)


def test_daily_gap_stops_watermark_before_hole(db_session, monkeypatch):
    import astock.services.imports.pipeline as pipeline

    monkeypatch.setattr(pipeline, "last_settled_date", lambda market="cn": "2026-01-08")
    upsert_sync_meta(
        db_session,
        "point",
        last_synced_date="2026-01-05",
        status=SyncStatus.PARTIAL_FAILURE,
    )
    starts: list[str] = []

    def fetch(start: str) -> FetchResult:
        starts.append(start)
        return FetchResult(
            records=[
                {
                    "date": "2026-01-06",
                    "index_code": "000001",
                    "close": 1.0,
                    "cached_at": "t",
                },
                {
                    "date": "2026-01-08",
                    "index_code": "000001",
                    "close": 1.2,
                    "cached_at": "t",
                },
            ]
        )

    spec = DailyImportSpec(
        table_name="point",
        model=Point,
        conflict_cols=["date", "index_code"],
        fetch=fetch,
        source_key="point",
        failure_message="点位失败",
        log_label="点位",
    )
    result = run_daily_import(db_session, spec, raise_on_failed=False)
    assert result.status == SyncStatus.PARTIAL_FAILURE
    assert get_sync_meta(db_session, "point").last_synced_date == "2026-01-06"

    def fetch_again(start: str) -> FetchResult:
        starts.append(start)
        return FetchResult(records=[], ok=False, errors=["空"])

    spec.fetch = fetch_again
    run_daily_import(db_session, spec, raise_on_failed=False)
    assert starts[-1] == "2026-01-07"
    assert "2026-01-06" not in starts[1:]


def test_macro_without_cpi_keeps_watermark_and_does_not_skip(db_session):
    from astock.services.imports._macro_domain import run_macro_import, should_skip_macro

    upsert_sync_meta(
        db_session,
        "us_macro",
        last_synced_date="2026-08",
        status=SyncStatus.SUCCESS,
    )

    def fetch() -> FetchResult:
        return FetchResult(
            records=[
                {
                    "region": "us",
                    "period": "2026-09",
                    "metric": "fed_rate_upper",
                    "value": 4.5,
                }
            ]
        )

    result = run_macro_import(
        db_session,
        region="us",
        sync_table="us_macro",
        refresh_day=15,
        fetch_fn=fetch,
        log_label="美国宏观",
        required_metrics=("cpi_yoy", "fed_rate_upper"),
    )
    meta = get_sync_meta(db_session, "us_macro")
    assert result.status == SyncStatus.PARTIAL_FAILURE
    assert meta.last_synced_date == "2026-08"
    skip, _ = should_skip_macro(
        db_session, region="us", sync_table="us_macro", refresh_day=15
    )
    assert skip is False


def test_macro_missing_expected_metric_does_not_advance(db_session):
    from astock.services.imports._macro_domain import run_macro_import, should_skip_macro

    upsert_sync_meta(
        db_session,
        "us_macro",
        last_synced_date="2026-08",
        status=SyncStatus.SUCCESS,
    )

    def fetch() -> FetchResult:
        return FetchResult(
            records=[
                {"region": "us", "period": "2026-09", "metric": "cpi_yoy", "value": 2.4},
            ]
        )

    result = run_macro_import(
        db_session,
        region="us",
        sync_table="us_macro",
        refresh_day=15,
        fetch_fn=fetch,
        log_label="美国宏观",
        required_metrics=("cpi_yoy", "fed_rate_upper"),
    )
    meta = get_sync_meta(db_session, "us_macro")
    assert result.status == SyncStatus.PARTIAL_FAILURE
    assert meta.last_synced_date == "2026-08"
    skip, _ = should_skip_macro(
        db_session, region="us", sync_table="us_macro", refresh_day=15
    )
    assert skip is False


def test_global_asset_partial_failure_keeps_old_watermark(db_session, monkeypatch):
    import astock.services.imports.global_assets as ga

    upsert_sync_meta(
        db_session,
        "asset_high",
        last_synced_date="2026-01-02",
        status=SyncStatus.SUCCESS,
    )
    monkeypatch.setattr(ga, "fetch_all_assets", lambda assets: {})
    result = ga.refresh_asset_highs(db_session)
    meta = get_sync_meta(db_session, "asset_high")
    assert result.status != SyncStatus.SUCCESS
    assert meta.last_synced_date == "2026-01-02"


def test_stock_success_prefix_is_not_refetched(db_session, monkeypatch):
    import astock.services.imports.stock as stock

    for day in ("2026-01-05", "2026-01-06", "2026-01-07"):
        db_session.add(
            Turnover(
                date=day,
                sse_amount=1,
                szse_amount=1,
                turnover=2,
                cached_at="t",
            )
        )
    db_session.commit()

    @contextmanager
    def session():
        yield object()

    asked: list[str] = []

    def names(_day: str) -> FetchResult:
        return FetchResult(records=[{"code": "600000", "name": "浦发银行"}])

    def amounts(day: str) -> FetchResult:
        asked.append(day)
        if day == "2026-01-06":
            return FetchResult(records=[], ok=False, errors=["空"])
        return FetchResult(records=[{"code": "600000", "amount": 100.0}])

    monkeypatch.setattr(stock, "baostock_session", session)
    monkeypatch.setattr(stock, "login_error", lambda _lg: None)
    monkeypatch.setattr(stock, "fetch_all_stock_codes_logged_in", names)
    monkeypatch.setattr(stock, "fetch_daily_astock_amounts_logged_in", amounts)

    bridge = SSEBridge()
    reporter = ProgressReporter(bridge.emit)
    result = _drain(stock.import_stock_gen(db_session, on_progress=reporter, bridge=bridge))
    assert result.status == SyncStatus.PARTIAL_FAILURE
    assert get_sync_meta(db_session, "stock_turnover").last_synced_date == "2026-01-05"
    assert db_session.get(StockTurnover, ("2026-01-05", "600000")) is not None

    asked.clear()
    with pytest.raises(Exception, match="个股切片导入失败"):
        _drain(stock.import_stock_gen(db_session, on_progress=reporter, bridge=bridge))
    assert "2026-01-05" not in asked
    assert asked[0] == "2026-01-06"


def test_closes_cover_settled_ignores_exchange_holiday(monkeypatch):
    import astock.core.price_utils as price_utils

    monkeypatch.setattr(price_utils, "last_settled_date", lambda market="cn": "2025-10-07")
    assert closes_cover_settled({"2025-09-30": 3200.0}, "cn") is True

    monkeypatch.setattr(price_utils, "last_settled_date", lambda market="cn": "2025-10-09")
    assert closes_cover_settled({"2025-09-30": 3200.0}, "cn") is False


def test_usd_spot_scale_rejects_order_of_magnitude_gap():
    from astock.datasets.market_overview.usd_index import _align_spot_quote

    history = {"2026-01-08": 100.0}
    closes, err = _align_spot_quote(
        {"quote_date": "2026-01-08", "current": 30000.0, "prev": None},
        history,
        hundredths=True,
    )
    assert closes == {}
    assert err
    scaled, scale_err = _align_spot_quote(
        {"quote_date": "2026-01-08", "current": 10000.0, "prev": None},
        history,
        hundredths=True,
    )
    assert scale_err is None
    assert scaled["2026-01-08"] == pytest.approx(100.0)


def test_import_password_lockout():
    from astock.core.errors import AppError
    from astock.core.rate_limit import FailureLockout

    lock = FailureLockout(max_failures=5, lock_seconds=900)
    for _ in range(5):
        lock.fail("10.0.0.1")
    with pytest.raises(AppError) as caught:
        lock.check("10.0.0.1")
    assert caught.value.status_code == 429
