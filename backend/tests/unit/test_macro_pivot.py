"""宏观长表 pivot 与加载过滤:queries/_common 纯计算。"""

from astock.models.macro import MacroValue
from astock.services.queries._common import (
    latest_period_with,
    load_macro_rows,
    pivot_macro_rows,
)

_CACHED_AT = "2026-01-01T00:00:00+00:00"
_CN_METRICS = (
    "cpi_yoy",
    "ppi_yoy",
    "pmi_manufacturing",
    "pmi_non_manufacturing",
    "consumer_confidence",
)


def _seed(db, region, period, metric, value):  # noqa: ANN001
    db.add(
        MacroValue(
            region=region, period=period, metric=metric, value=value, cached_at=_CACHED_AT
        )
    )
    db.commit()


class TestPivotMacroRows:
    def test_groups_by_period_and_fills_missing_with_none(self):
        rows = [
            MacroValue(region="cn", period="2026-08", metric="cpi_yoy", value=2.1, cached_at=_CACHED_AT),
            MacroValue(region="cn", period="2026-08", metric="ppi_yoy", value=-1.3, cached_at=_CACHED_AT),
            MacroValue(region="cn", period="2026-09", metric="cpi_yoy", value=2.4, cached_at=_CACHED_AT),
        ]
        pivoted = pivot_macro_rows(rows, _CN_METRICS)
        assert pivoted["2026-08"] == {
            "cpi_yoy": 2.1,
            "ppi_yoy": -1.3,
            "pmi_manufacturing": None,
            "pmi_non_manufacturing": None,
            "consumer_confidence": None,
        }
        assert pivoted["2026-09"]["cpi_yoy"] == 2.4

    def test_empty_rows_yield_empty_dict(self):
        assert pivot_macro_rows([], _CN_METRICS) == {}


class TestLoadMacroRows:
    def test_filters_region_period_and_metrics(self, db_session):
        _seed(db_session, "cn", "2026-07", "cpi_yoy", 0.5)
        _seed(db_session, "cn", "2026-08", "cpi_yoy", 2.1)
        _seed(db_session, "cn", "2026-08", "pmi_manufacturing", 50.2)
        _seed(db_session, "us", "2026-08", "cpi_yoy", 3.0)

        rows = load_macro_rows(
            db_session, region="cn", metrics=("cpi_yoy", "pmi_manufacturing"),
            start_period="2026-08",
        )
        assert [(r.region, r.period, r.metric, r.value) for r in rows] == [
            ("cn", "2026-08", "cpi_yoy", 2.1),
            ("cn", "2026-08", "pmi_manufacturing", 50.2),
        ]

    def test_orders_by_period_then_metric(self, db_session):
        _seed(db_session, "cn", "2026-09", "ppi_yoy", -1.0)
        _seed(db_session, "cn", "2026-08", "ppi_yoy", -1.3)
        _seed(db_session, "cn", "2026-08", "cpi_yoy", 2.1)

        rows = load_macro_rows(
            db_session, region="cn", metrics=("cpi_yoy", "ppi_yoy"), start_period="2000-01"
        )
        assert [(r.period, r.metric) for r in rows] == [
            ("2026-08", "cpi_yoy"),
            ("2026-08", "ppi_yoy"),
            ("2026-09", "ppi_yoy"),
        ]


class TestLatestPeriodWith:
    def test_scans_reversed_for_first_predicate_match(self):
        class P:
            def __init__(self, period, ok):
                self.period = period
                self.ok = ok

        points = [P("2026-08", False), P("2026-09", False), P("2026-10", True)]
        assert latest_period_with(points, predicate=lambda p: p.ok) == "2026-10"

    def test_falls_back_to_last_period(self):
        class P:
            def __init__(self, period, ok):
                self.period = period
                self.ok = ok

        points = [P("2026-08", True), P("2026-09", False)]
        assert latest_period_with(points, predicate=lambda p: p.ok) == "2026-08"

    def test_empty_returns_none(self):
        assert latest_period_with([], predicate=lambda p: True) is None
