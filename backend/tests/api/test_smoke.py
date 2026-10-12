"""冒烟测试:app 可拉起、信封契约与空库行为。"""


def test_sync_status_empty_db_returns_envelope(client):
    resp = client.get("/api/v1/admin/data/sync-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    data = body["data"]
    assert set(data.keys()) == {
        "turnover", "point", "stock", "global_assets", "us_macro", "cn_macro",
    }
    for dataset_status in data.values():
        assert dataset_status == {
            "last_synced_date": None,
            "last_synced_at": None,
            "status": None,
        }


def test_bull_market_point_empty_db_returns_zero_stats(client):
    resp = client.get("/api/v1/analysis/bull-markets/point")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    indices = body["data"]["indices"]
    assert [i["index_code"] for i in indices] == ["000001", "000300", "399006", "000688"]
    assert all(i["total_days"] == 0 for i in indices)
