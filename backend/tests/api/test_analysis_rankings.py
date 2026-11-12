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


class TestTurnoverSeries:
    def test_invalid_range_maps_to_422_envelope(self, client):
        resp = client.get("/api/v1/analysis/turnover/series?range=2y")
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == 1001
        assert body["data"] is None

    def test_default_range_is_one_year_from_latest_date(self, client, seed):
        seed.turnovers(
            [
                ("2024-06-01", 0.4e12, 0.4e12),  # 截止日前一日,排除
                ("2024-06-02", 0.5e12, 0.5e12),  # 近一年起点
                ("2025-06-02", 1.0e12, 1.0e12),  # 库内最新日
            ]
        )
        data = client.get("/api/v1/analysis/turnover/series").json()["data"]
        assert data["range"] == "1y"
        assert data["latest_date"] == "2025-06-02"
        assert [item["date"] for item in data["items"]] == [
            "2024-06-02",
            "2025-06-02",
        ]

    def test_five_year_and_all_windows(self, client, seed):
        seed.turnovers(
            [
                ("2019-02-27", 0.1e12, 0.1e12),
                ("2019-02-28", 0.2e12, 0.2e12),
                ("2024-02-29", 0.3e12, 0.3e12),
            ]
        )
        five_year = client.get(
            "/api/v1/analysis/turnover/series?range=5y"
        ).json()["data"]
        assert [item["date"] for item in five_year["items"]] == [
            "2019-02-28",
            "2024-02-29",
        ]

        everything = client.get(
            "/api/v1/analysis/turnover/series?range=all"
        ).json()["data"]
        assert [item["date"] for item in everything["items"]] == [
            "2019-02-27",
            "2019-02-28",
            "2024-02-29",
        ]

    def test_leap_day_one_year_falls_back_to_feb_28(self, client, seed):
        seed.turnovers(
            [
                ("2023-02-27", 0.1e12, 0.1e12),
                ("2023-02-28", 0.2e12, 0.2e12),
                ("2024-02-29", 0.3e12, 0.3e12),
            ]
        )
        data = client.get("/api/v1/analysis/turnover/series?range=1y").json()["data"]
        assert [item["date"] for item in data["items"]] == [
            "2023-02-28",
            "2024-02-29",
        ]

    def test_top_rank_uses_global_history_not_window(self, client, seed):
        seed.turnovers(
            [
                ("2020-01-02", 9.0e12, 0.0),  # 全量第 1,落在近一年窗口外
                ("2025-06-01", 1.0e12, 0.0),
                ("2025-06-02", 2.0e12, 0.0),
            ]
        )
        data = client.get("/api/v1/analysis/turnover/series?range=1y").json()["data"]
        ranks = {item["date"]: item["top_rank"] for item in data["items"]}
        assert ranks == {"2025-06-01": 3, "2025-06-02": 2}

    def test_top_rank_marks_only_highest_twenty(self, client, seed):
        seed.turnovers(
            [(f"2024-01-{day:02d}", float(day) * 1e11, 0.0) for day in range(1, 22)]
        )
        data = client.get("/api/v1/analysis/turnover/series?range=all").json()["data"]
        ranks = {item["date"]: item["top_rank"] for item in data["items"]}
        assert ranks["2024-01-21"] == 1
        assert ranks["2024-01-02"] == 20
        assert ranks["2024-01-01"] is None
        assert data["items"][0]["sse_amount"] == 1e11
        assert data["items"][0]["turnover"] == 1e11

    def test_empty_db_returns_empty_items(self, client):
        resp = client.get("/api/v1/analysis/turnover/series")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["latest_date"] is None
        assert data["items"] == []


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
