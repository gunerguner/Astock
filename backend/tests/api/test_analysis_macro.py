"""中美宏观端点:长表 pivot 形状、start 过滤与水位元数据。"""


class TestCnMacro:
    def test_pivot_shape_and_start_filter(self, client, seed):
        for metric, value in (
            ("cpi_yoy", 2.1),
            ("ppi_yoy", -1.3),
            ("pmi_manufacturing", 50.2),
            ("pmi_non_manufacturing", 51.0),
            ("consumer_confidence", 88.5),
        ):
            seed.macro("cn", "2026-08", metric, value)
        seed.macro("cn", "2026-09", "cpi_yoy", 2.4)
        # us 行不应混入 cn 查询
        seed.macro("us", "2026-08", "cpi_yoy", 3.0)

        resp = client.get("/api/v1/analysis/cn-macro?start=2026-09")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["start"] == "2026-09"
        assert [p["period"] for p in data["points"]] == ["2026-09"]
        point = data["points"][0]
        assert point["cpi_yoy"] == 2.4
        # 该月缺失指标保持 None,不抛错
        assert point["ppi_yoy"] is None
        assert data["latest_period"] == "2026-09"

    def test_missing_metrics_render_as_none_per_period(self, client, seed):
        seed.macro("cn", "2026-08", "cpi_yoy", 2.1)
        data = client.get("/api/v1/analysis/cn-macro?start=2026-08").json()["data"]
        assert len(data["points"]) == 1
        assert data["points"][0]["cpi_yoy"] == 2.1
        assert data["points"][0]["pmi_manufacturing"] is None

    def test_empty_db_returns_empty_points(self, client):
        resp = client.get("/api/v1/analysis/cn-macro")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["points"] == []
        assert data["latest_period"] is None

    def test_start_validation(self, client):
        resp = client.get("/api/v1/analysis/cn-macro?start=2026-9")
        assert resp.status_code == 422
        assert resp.json()["code"] == 1001


class TestUsMacro:
    def test_pivot_and_latest_period_prefers_cpi(self, client, seed):
        seed.macro("us", "2026-08", "cpi_yoy", 2.9)
        seed.macro("us", "2026-08", "fed_rate_upper", 5.25)
        seed.macro("us", "2026-09", "fed_rate_upper", 5.0)  # 晚于最新 CPI 的纯利率月份

        resp = client.get("/api/v1/analysis/us-macro?start=2026-08")
        data = resp.json()["data"]
        # 2026-09 只有利率,应被丢弃
        assert [p["period"] for p in data["points"]] == ["2026-08"]
        assert data["points"][0]["cpi_yoy"] == 2.9
        assert data["points"][0]["fed_rate_upper"] == 5.25
        assert data["latest_period"] == "2026-08"

    def test_rate_only_month_within_cpi_range_is_kept(self, client, seed):
        seed.macro("us", "2026-08", "cpi_yoy", 2.9)
        seed.macro("us", "2026-09", "fed_rate_upper", 5.0)
        seed.macro("us", "2026-10", "cpi_yoy", 2.7)
        data = client.get("/api/v1/analysis/us-macro?start=2026-08").json()["data"]
        # 09 月夹在两个 CPI 月之间,保留且利率有值
        assert [p["period"] for p in data["points"]] == [
            "2026-08", "2026-09", "2026-10",
        ]
        assert data["points"][1]["fed_rate_upper"] == 5.0
        assert data["points"][1]["cpi_yoy"] is None

    def test_last_synced_at_from_sync_meta(self, client, seed):
        seed.sync_meta("us_macro", "2026-10-01")
        data = client.get("/api/v1/analysis/us-macro").json()["data"]
        assert data["last_synced_at"] == "2026-01-01T00:00:00+00:00"

    def test_empty_db(self, client):
        resp = client.get("/api/v1/analysis/us-macro")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["points"] == []
        assert data["latest_period"] is None
