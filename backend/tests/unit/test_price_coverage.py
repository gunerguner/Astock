"""价格缓存覆盖判定：休市日不误判缺口。"""

from astock.core.price_utils import closes_cover_settled


def test_closes_cover_settled_ignores_exchange_holiday(monkeypatch):
    import astock.core.price_utils as price_utils

    monkeypatch.setattr(price_utils, "last_settled_date", lambda market="cn": "2025-10-07")
    assert closes_cover_settled({"2025-09-30": 3200.0}, "cn") is True

    monkeypatch.setattr(price_utils, "last_settled_date", lambda market="cn": "2025-10-09")
    assert closes_cover_settled({"2025-09-30": 3200.0}, "cn") is False