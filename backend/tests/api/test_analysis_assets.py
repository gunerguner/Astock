"""全球资产水位与市场概览端点:缓存路径、结论标签与 force_refresh。"""

import pytest

from astock.services.cache.closes import ClosesFetchResult

_AAPL_CLOSES = {
    "2026-09-24": 245.0,
    "2026-09-25": 248.0,
    "2026-09-28": 250.0,
    "2026-09-29": 249.0,
    "2026-09-30": 250.0,
}

_CN_INDEX_CLOSES = {
    "2026-09-25": 3800.0,
    "2026-09-28": 3850.0,
    "2026-09-29": 3900.0,
    "2026-09-30": 3950.0,
}


@pytest.fixture
def patch_price_cache(monkeypatch):
    """替换全球资产收盘价缓存,避开 AkShare/Redis 真实路径。"""
    calls: list[dict] = []

    def _fake(assets, force_refresh: bool = False):  # noqa: ANN001, ANN202
        calls.append({"force_refresh": force_refresh})
        return ClosesFetchResult(closes={"AAPL": _AAPL_CLOSES}, errors=[])

    monkeypatch.setattr(
        "astock.services.queries.global_asset._ensure_price_cache", _fake
    )
    return calls


class TestAssetPriceLevels:
    def test_price_level_fields_and_conclusion(self, client, seed, patch_price_cache):
        seed.asset_high("AAPL", "苹果", "stock", 300.0, "2024-12-16")
        seed.sync_meta("asset_high", "2026-09-30")

        resp = client.get("/api/v1/analysis/asset-price-levels")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["latest_trading_date"] == "2026-09-30"

        aapl = next(i for i in data["items"] if i["ticker"] == "AAPL")
        assert aapl["name"] == "苹果"
        assert aapl["current_price"] == 250.0
        assert aapl["all_time_high"] == 300.0
        assert aapl["ath_date"] == "2024-12-16"
        # (250-300)/300*100 = -16.67
        assert aapl["percentage_diff"] == -16.67
        assert aapl["conclusion"] == "moderatePullback"
        assert aapl["ath_days"] > 0
        # (250-249)/249*100 ≈ 0.40;仅 5 个交易日点 < 周基准偏移 6 → 周涨跌为空
        assert aapl["daily_change"] == 0.4
        assert aapl["weekly_change"] is None

    def test_current_above_ath_updates_high(self, client, seed, patch_price_cache):
        seed.asset_high("AAPL", "苹果", "stock", 240.0, "2024-12-16")
        seed.sync_meta("asset_high", "2026-09-30")

        aapl = next(
            i
            for i in client.get("/api/v1/analysis/asset-price-levels").json()["data"][
                "items"
            ]
            if i["ticker"] == "AAPL"
        )
        assert aapl["all_time_high"] == 250.0
        assert aapl["ath_date"] == "2026-09-30"
        assert aapl["percentage_diff"] == 0.0
        assert aapl["conclusion"] == "nearAth"

    def test_empty_db_rejected_before_any_fetch(self, client, patch_price_cache):
        resp = client.get("/api/v1/analysis/asset-price-levels")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 1001
        assert "全球资产历史最高点数据为空" in body["message"]
        assert patch_price_cache == []

    def test_force_refresh_forwarded(self, client, seed, patch_price_cache):
        seed.asset_high("AAPL", "苹果", "stock", 300.0, "2024-12-16")
        seed.sync_meta("asset_high", "2026-09-30")
        client.get("/api/v1/analysis/asset-price-levels?force_refresh=true")
        assert patch_price_cache[0]["force_refresh"] is True


@pytest.fixture
def patch_overview_cache(monkeypatch):
    def _fake(force_refresh: bool = False) -> ClosesFetchResult:
        return ClosesFetchResult(
            closes={
                "cn_stocks:000001": _CN_INDEX_CLOSES,
                "us_stocks:道琼斯": {"2026-09-30": 45000.0},
            },
            errors=[],
        )

    monkeypatch.setattr(
        "astock.services.queries.market_overview.service._ensure_closes", _fake
    )


class TestMarketOverview:
    def test_categories_shape_with_success_and_error_items(
        self, client, patch_overview_cache
    ):
        resp = client.get("/api/v1/analysis/market-overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert [c["key"] for c in data["categories"]] == [
            "us_stocks",
            "cn_stocks",
            "precious_metals",
            "forex",
            "commodities",
            "bonds",
        ]

        cn = next(c for c in data["categories"] if c["key"] == "cn_stocks")
        sse = next(i for i in cn["items"] if i["code"] == "000001")
        assert sse["current_price"] == 3950.0
        # (3950-3900)/3900*100 ≈ 1.28
        assert sse["daily_change"] == 1.28
        assert "error" not in sse

        szse = next(i for i in cn["items"] if i["code"] == "000300")
        assert szse["error"] == "数据获取失败"

    def test_cache_error_list_empty_when_fetch_ok(self, client, patch_overview_cache):
        data = client.get("/api/v1/analysis/market-overview").json()["data"]
        assert data["errors"] == []

    def test_latest_trading_date_falls_back_to_settled_date(
        self, client, patch_overview_cache
    ):
        data = client.get("/api/v1/analysis/market-overview").json()["data"]
        # closes 锚点(2026-09-30)或结算日兜底,均不早于 2026-09
        assert data["latest_trading_date"] >= "2026-09-30"
