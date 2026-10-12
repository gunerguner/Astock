"""牛市点位/成交额端点:统计正确性、阈值参数与空库行为。"""

from astock.config import BULL_MARKETS

_2015 = BULL_MARKETS["2015"]
_2021 = BULL_MARKETS["2021"]


def _items_by_market(data: dict, index_code: str) -> dict:
    stats = next(i for i in data["indices"] if i["index_code"] == index_code)
    return {item["market"]: item for item in stats["items"]}


class TestBullMarketPoint:
    def test_threshold_counts_only_days_above_within_period(self, client, seed):
        # 上证(默认阈值 4000):2015 区间 3 天达标 + 1 天未达标;2021 区间 1 天达标
        seed.points(
            [
                (_2015["start"], "000001", 5000.0),
                ("2015-01-05", "000001", 5200.0),
                ("2015-02-06", "000001", 5100.0),
                ("2015-03-09", "000001", 3000.0),
                (_2021["start"], "000001", 4500.0),
                # 区间外的高点不应计入任何牛市
                ("2013-01-04", "000001", 9000.0),
            ]
        )
        resp = client.get("/api/v1/analysis/bull-markets/point")
        assert resp.status_code == 200
        data = resp.json()["data"]

        stats_000001 = next(i for i in data["indices"] if i["index_code"] == "000001")
        assert stats_000001["threshold"] == 4000
        assert stats_000001["total_days"] == 4

        items = _items_by_market(data, "000001")
        assert items["2015"]["days"] == 3
        assert items["2015"]["max_value"] == 5200.0
        assert items["2021"]["days"] == 1
        assert items["2007-2009"]["days"] == 0
        assert items["2007-2009"]["max_value"] is None

    def test_items_sorted_by_end_desc(self, client, seed):
        seed.point("2015-01-05", "000001", 5000.0)
        data = client.get("/api/v1/analysis/bull-markets/point").json()["data"]
        stats = next(i for i in data["indices"] if i["index_code"] == "000001")
        ends = [item["end"] for item in stats["items"]]
        assert ends == sorted(ends, reverse=True)

    def test_index_not_available_in_early_bull_markets(self, client, seed):
        # 科创50 available_from=2020-07-23:早于该日的区间 not_available
        seed.point("2025-01-05", "000688", 1300.0)
        data = client.get("/api/v1/analysis/bull-markets/point").json()["data"]
        items = _items_by_market(data, "000688")
        assert items["2007-2009"]["not_available"] is True
        assert items["2015"]["not_available"] is True
        assert items["2021"]["not_available"] is False  # end=2022-06-30 晚于发布日
        assert items["2024"]["not_available"] is False

    def test_custom_threshold_query_param(self, client, seed):
        seed.point("2015-01-05", "000001", 5000.0)
        resp = client.get("/api/v1/analysis/bull-markets/point?threshold_000001=4500")
        assert resp.status_code == 200
        items = _items_by_market(resp.json()["data"], "000001")
        assert items["2015"]["days"] == 1

        resp = client.get("/api/v1/analysis/bull-markets/point?threshold_000001=5500")
        items = _items_by_market(resp.json()["data"], "000001")
        assert items["2015"]["days"] == 0


class TestBullMarketTurnover:
    def test_empty_db_maps_to_app_error(self, client):
        resp = client.get("/api/v1/analysis/bull-markets/turnover")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == 9000
        assert body["message"] == "成交额数据为空，请先导入数据"

    def test_turnover_stats_with_default_threshold(self, client, seed):
        # 默认阈值 2e12( turnover = sse + szse )
        seed.turnovers(
            [
                ("2015-04-20", 1.2e12, 1.0e12),  # 2.2e12 达标
                ("2015-05-18", 1.1e12, 1.1e12),  # 2.2e12 达标
                ("2015-06-01", 0.5e12, 0.4e12),  # 未达标
                ("2021-02-18", 1.5e12, 1.4e12),  # 2.9e12 达标
            ]
        )
        resp = client.get("/api/v1/analysis/bull-markets/turnover")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["threshold"] == 2e12
        assert data["total_days"] == 3
        items = {item["market"]: item for item in data["items"]}
        assert items["2015"]["days"] == 2
        assert items["2015"]["max_value"] == 2.2e12
        assert items["2021"]["days"] == 1

    def test_custom_threshold(self, client, seed):
        seed.turnovers([("2015-04-20", 1.2e12, 1.0e12)])
        resp = client.get("/api/v1/analysis/bull-markets/turnover?threshold=3e12")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["threshold"] == 3e12
        assert data["total_days"] == 0
