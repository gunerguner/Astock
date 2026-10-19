"""rankings service 纯计算:排序、TopN、牛市区间与未知区间错误。"""

import pytest
from fastapi import status

from astock.core.errors import AppError, ErrorCode
from astock.models.stock_turnover import StockTurnover
from astock.models.turnover import Turnover
from astock.services.queries.rankings import stock_ranking, turnover_ranking

_CACHED_AT = "2026-01-01T00:00:00+00:00"


def _seed_turnovers(db, rows):  # noqa: ANN001
    db.add_all(
        Turnover(
            date=d, sse_amount=sse, szse_amount=szse, turnover=sse + szse,
            cached_at=_CACHED_AT,
        )
        for d, sse, szse in rows
    )
    db.commit()


def _seed_stocks(db, rows):  # noqa: ANN001
    db.add_all(
        StockTurnover(date=d, code=c, name=n, amount=a, cached_at=_CACHED_AT)
        for d, c, n, a in rows
    )
    db.commit()


def test_turnover_ranking_orders_desc_and_limits(db_session):
    _seed_turnovers(
        db_session,
        [
            ("2015-04-20", 1.0e12, 1.0e12),
            ("2015-05-18", 1.3e12, 1.3e12),
            ("2015-06-01", 0.5e12, 0.5e12),
        ],
    )
    resp = turnover_ranking(db_session, top=2)
    assert [i.date for i in resp.items] == ["2015-05-18", "2015-04-20"]
    assert [i.rank for i in resp.items] == [1, 2]
    assert resp.top == 2
    assert resp.bull_market is None


def test_turnover_ranking_bull_market_filter(db_session):
    _seed_turnovers(db_session, [("2015-04-20", 0.6e12, 0.6e12)])
    resp = turnover_ranking(db_session, bull_market="2015")
    assert [i.date for i in resp.items] == ["2015-04-20"]
    assert resp.bull_market == "2015"


def test_stock_ranking_orders_desc(db_session):
    _seed_stocks(
        db_session,
        [
            ("2015-04-20", "601398", "工商银行", 8.8e10),
            ("2015-04-21", "601988", "中国银行", 9.9e10),
        ],
    )
    resp = stock_ranking(db_session, top=5)
    assert [(i.rank, i.code, i.amount) for i in resp.items] == [
        (1, "601988", 9.9e10),
        (2, "601398", 8.8e10),
    ]


def test_unknown_bull_market_raises_validation_error(db_session):
    with pytest.raises(AppError) as exc_info:
        turnover_ranking(db_session, bull_market="nope")
    err = exc_info.value
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert err.status_code == status.HTTP_400_BAD_REQUEST
