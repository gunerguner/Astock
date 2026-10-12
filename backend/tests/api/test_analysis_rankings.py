"""成交额/个股排名端点:TopN、排序与牛市区间过滤。"""


class TestTurnoverRanking:
    def test_ranked_by_turnover_desc_with_top_limit(self, client, seed):
        seed.turnovers(
            [
                ("2015-04-20", 1.0e12, 1.0e12),  # 2.0e12
                ("2015-05-18", 1.3e12, 1.3e12),  # 2.6e12 最高
                ("2015-06-01", 0.5e12, 0.5e12),  # 1.0e12
            ]
        )
        resp = client.get("/api/v1/analysis/turnover/ranking?top=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["top"] == 2
        assert data["bull_market"] is None
        assert [(i["rank"], i["date"]) for i in data["items"]] == [
            (1, "2015-05-18"),
            (2, "2015-04-20"),
        ]
        assert data["items"][0]["turnover"] == 2.6e12

    def test_bull_market_filter(self, client, seed):
        seed.turnovers(
            [
                ("2015-04-20", 0.6e12, 0.6e12),
                ("2013-01-04", 3.0e12, 3.0e12),  # 区间外,总量更高
            ]
        )
        resp = client.get("/api/v1/analysis/turnover/ranking?bull_market=2015")
        data = resp.json()["data"]
        assert data["bull_market"] == "2015"
        assert [i["date"] for i in data["items"]] == ["2015-04-20"]

    def test_bull_market_all_returns_everything_with_none_marker(self, client, seed):
        seed.turnovers([("2015-04-20", 0.6e12, 0.6e12), ("2013-01-04", 3.0e12, 3.0e12)])
        data = client.get(
            "/api/v1/analysis/turnover/ranking?bull_market=all"
        ).json()["data"]
        assert data["bull_market"] is None
        assert len(data["items"]) == 2

    def test_empty_db_returns_empty_items(self, client):
        resp = client.get("/api/v1/analysis/turnover/ranking")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []


class TestStockRanking:
    def test_ranked_by_amount_desc(self, client, seed):
        seed.stock_turnover("2015-04-20", "601398", "工商银行", 8.8e10)
        seed.stock_turnover("2015-04-21", "601988", "中国银行", 9.9e10)
        seed.stock_turnover("2015-04-22", "600030", "中信证券", 7.7e10)
        resp = client.get("/api/v1/analysis/stock/ranking?top=2")
        data = resp.json()["data"]
        assert [(i["rank"], i["code"]) for i in data["items"]] == [
            (1, "601988"),
            (2, "601398"),
        ]

    def test_bull_market_filter_out_of_range(self, client, seed):
        seed.stock_turnover("2015-04-20", "601398", "工商银行", 8.8e10)
        seed.stock_turnover("2013-01-04", "600030", "中信证券", 9.9e10)
        data = client.get(
            "/api/v1/analysis/stock/ranking?bull_market=2015"
        ).json()["data"]
        assert [i["code"] for i in data["items"]] == ["601398"]
