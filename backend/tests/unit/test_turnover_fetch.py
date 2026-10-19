"""成交额拉取：单侧失败不补零、静默空侧不算成功。"""

from contextlib import contextmanager

import pandas as pd


@contextmanager
def _fake_session():
    yield object()


def test_turnover_one_sided_failure_does_not_zero_fill(monkeypatch):
    import astock.datasets.turnover as mod
    from astock.providers.baostock.client import BaostockQueryError

    monkeypatch.setattr(mod, "last_settled_date", lambda market="cn": "2026-01-08")
    monkeypatch.setattr(mod, "baostock_session", _fake_session)
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
    monkeypatch.setattr(mod, "baostock_session", _fake_session)
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