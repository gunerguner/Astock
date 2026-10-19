"""美元指数现货与 K 线的数量级对齐。"""

import pytest


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


def test_usd_spot_unscaled_passes_through():
    from astock.datasets.market_overview.usd_index import _align_spot_quote

    history = {"2026-01-08": 100.0}
    closes, err = _align_spot_quote(
        {"quote_date": "2026-01-08", "current": 99.5, "prev": 100.2},
        history,
        hundredths=False,
    )
    assert err is None
    assert closes["2026-01-08"] == pytest.approx(99.5)
    assert closes["2026-01-07"] == pytest.approx(100.2)