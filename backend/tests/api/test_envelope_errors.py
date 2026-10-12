"""错误信封契约:校验错误、业务错误与统一 code/message 映射。"""


class TestValidationErrors:
    def test_ranking_top_out_of_range_maps_to_422_envelope(self, client):
        resp = client.get("/api/v1/analysis/turnover/ranking?top=0")
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == 1001
        assert body["message"] == "参数校验失败"
        assert body["data"] is None

    def test_negative_threshold_rejected(self, client):
        resp = client.get("/api/v1/analysis/bull-markets/turnover?threshold=-1")
        assert resp.status_code == 422
        assert resp.json()["code"] == 1001

    def test_unknown_dataset_rejected(self, client):
        resp = client.post("/api/v1/admin/data/import/stream?dataset=stocks")
        assert resp.status_code == 422
        assert resp.json()["code"] == 1001


class TestBusinessErrors:
    def test_unknown_bull_market_maps_to_400(self, client):
        resp = client.get("/api/v1/analysis/turnover/ranking?bull_market=nope")
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 1001
        assert "未知牛市区间" in body["message"]

    def test_empty_turnover_maps_to_internal_error(self, client):
        # 现状行为:require_rows 抛默认 AppError(500/9000)
        resp = client.get("/api/v1/analysis/bull-markets/turnover")
        assert resp.status_code == 500
        assert resp.json()["code"] == 9000

    def test_empty_asset_high_rejected_as_validation_error(self, client):
        resp = client.get("/api/v1/analysis/asset-price-levels")
        assert resp.status_code == 400
        assert resp.json()["code"] == 1001


class TestSuccessEnvelope:
    def test_success_envelope_shape(self, client, seed):
        seed.turnovers([("2015-04-20", 1.2e12, 1.0e12)])
        body = client.get("/api/v1/analysis/turnover/ranking?top=1").json()
        assert set(body.keys()) == {"code", "message", "data"}
        assert body["code"] == 0
        assert body["message"] == "success"
        assert body["data"]["top"] == 1
