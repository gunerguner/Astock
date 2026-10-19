"""bull_market_stats 纯计算:区间过滤、极值与 not_available 骨架。"""

import pytest

from astock.config import BULL_MARKETS
from astock.models.turnover import Turnover
from astock.services.queries.bull_market_stats import build_bull_market_stats

_2015 = BULL_MARKETS["2015"]


def _seed_turnovers(db, rows):  # noqa: ANN001
    db.add_all(
        Turnover(
            date=d, sse_amount=sse, szse_amount=szse, turnover=sse + szse,
            cached_at="2026-01-01T00:00:00+00:00",
        )
        for d, sse, szse in rows
    )
    db.commit()


def _build(db, threshold=2e12, **kwargs):  # noqa: ANN001, ANN003
    return build_bull_market_stats(db, Turnover, Turnover.turnover, threshold, **kwargs)


def test_counts_and_extremes_within_period(db_session):
    _seed_turnovers(
        db_session,
        [
            (_2015["start"], 1.2e12, 1.0e12),
            ("2015-01-05", 1.4e12, 1.2e12),  # 极值 2.6e12
            ("2015-02-06", 0.5e12, 0.4e12),  # 未达标
            ("2013-01-04", 5.0e12, 5.0e12),  # 区间外
        ],
    )
    resp = _build(db_session)

    by_market = {item.market: item for item in resp.items}
    assert by_market["2015"].days == 2
    assert by_market["2015"].max_value == 2.6e12
    assert by_market["2007-2009"].days == 0
    assert by_market["2007-2009"].max_value is None
    assert resp.total_days == 2


def test_available_from_marks_early_periods_not_available(db_session):
    _seed_turnovers(db_session, [("2025-01-05", 1.5e12, 1.4e12)])
    resp = _build(db_session, available_from="2020-07-23")
    by_market = {item.market: item for item in resp.items}
    # available_from(2020-07-23) 晚于两个历史区间的 end
    assert by_market["2007-2009"].not_available is True
    assert by_market["2015"].not_available is True
    assert by_market["2021"].not_available is False  # end=2022-06-30 晚于发布日
    assert by_market["2024"].not_available is False


def test_max_value_kept_when_all_days_below_threshold(db_session):
    _seed_turnovers(
        db_session,
        [
            ("2015-01-05", 0.4e12, 0.3e12),  # 0.7e12
            ("2015-02-06", 0.6e12, 0.5e12),  # 1.1e12，仍低于默认阈值
        ],
    )
    resp = _build(db_session)
    by_market = {item.market: item for item in resp.items}
    assert by_market["2015"].days == 0
    assert by_market["2015"].max_value == 1.1e12
    assert by_market["2007-2009"].max_value is None


def test_boundary_dates_inclusive(db_session):
    # 起止日当天均应计入
    _seed_turnovers(
        db_session,
        [
            (_2015["start"], 1.1e12, 1.0e12),
            (_2015["end"], 1.1e12, 1.0e12),
        ],
    )
    resp = _build(db_session)
    by_market = {item.market: item for item in resp.items}
    assert by_market["2015"].days == 2


@pytest.mark.parametrize(
    "threshold,amount,expected",
    [
        (2e12, 2e12, 0),  # 严格大于,等于不算
        (2e12, 2.000001e12, 1),
    ],
)
def test_threshold_strictness(db_session, threshold, amount, expected):
    _seed_turnovers(db_session, [("2015-01-05", amount / 2, amount / 2)])
    resp = _build(db_session, threshold)
    by_market = {item.market: item for item in resp.items}
    assert by_market["2015"].days == expected
    assert by_market["2015"].max_value == amount
