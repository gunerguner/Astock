"""admin 端点:sync-status 聚合与 SSE 流式导入(数据源全 mock,零出网)。"""

import json

import pytest

from astock.core.sync_status import SyncStatus
from astock.services.cache.closes import ClosesFetchResult
from astock.services.sync.results import ImportResult

_FIXED_AT = "2026-01-01T00:00:00+00:00"


def _result(status: SyncStatus = SyncStatus.SUCCESS, imported: int = 5) -> ImportResult:
    return ImportResult(
        imported=imported,
        total=imported,
        last_date="2026-10-04",
        last_synced_at=_FIXED_AT,
        status=status,
    )


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw in text.split("\n\n"):
        raw = raw.strip()
        if not raw:
            continue
        event = "message"
        data: dict = {}
        for line in raw.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        frames.append((event, data))
    return frames


class TestSyncStatus:
    def test_dataset_meta_reflected(self, client, seed):
        seed.sync_meta("turnover", "2026-10-04", SyncStatus.SUCCESS)
        seed.sync_meta("cn_macro", "2026-09", SyncStatus.PARTIAL_FAILURE)
        data = client.get("/api/v1/admin/data/sync-status").json()["data"]
        assert data["turnover"]["last_synced_date"] == "2026-10-04"
        assert data["turnover"]["status"] == "success"
        assert data["cn_macro"]["status"] == "partial_failure"

    def test_point_status_aggregates_per_index(self, client, seed):
        seed.sync_meta("point_000001", "2026-10-03")
        seed.sync_meta("point_000300", "2026-10-04")
        data = client.get("/api/v1/admin/data/sync-status").json()["data"]
        assert data["point"]["last_synced_date"] == "2026-10-04"
        assert data["point"]["status"] == "success"


@pytest.fixture
def patch_import_turnover(monkeypatch):
    calls: list[str] = []

    def _fake(db):  # noqa: ANN001
        calls.append("turnover")
        return _result()

    monkeypatch.setattr("astock.services.import_orchestrator.import_turnover", _fake)
    return calls


class TestImportStream:
    def test_single_dataset_emits_progress_then_done(
        self, client, patch_import_turnover
    ):
        resp = client.post("/api/v1/admin/data/import/stream?dataset=turnover")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert patch_import_turnover == ["turnover"]

        frames = _parse_sse(resp.text)
        assert [e for e, _ in frames] == ["progress", "progress", "done"]
        assert frames[0][1]["phase"] == "turnover"
        assert frames[0][1]["status"] == "running"
        assert frames[1][1]["status"] == "done"
        assert frames[1][1]["imported"] == 5
        done = frames[2][1]
        assert done["imported"] == 5
        assert done["status"] == "success"
        assert done["last_date"] == "2026-10-04"

    def test_source_failure_maps_to_error_frame(self, client, monkeypatch):
        def _boom(db):  # noqa: ANN001
            raise RuntimeError("baostock down")

        monkeypatch.setattr(
            "astock.services.import_orchestrator.import_turnover", _boom
        )
        resp = client.post("/api/v1/admin/data/import/stream?dataset=turnover")
        frames = _parse_sse(resp.text)
        assert frames[-1][0] == "error"
        assert "baostock down" in frames[-1][1]["message"]

    def test_all_runs_seven_phases_in_order(self, client, monkeypatch):
        def _stock_gen(db, on_progress=None, bridge=None):  # noqa: ANN001
            return _result(imported=1)
            yield  # pragma: no cover — 仅为生成器形态,供 StopIteration.value 取结果

        for name in (
            "import_turnover",
            "import_point",
            "refresh_asset_highs",
            "import_us_macro",
            "import_cn_macro",
        ):
            monkeypatch.setattr(
                f"astock.services.import_orchestrator.{name}",
                lambda db, _name=name: _result(imported=1),
            )
        monkeypatch.setattr(
            "astock.services.import_orchestrator.import_stock_gen", _stock_gen
        )
        monkeypatch.setattr(
            "astock.services.import_orchestrator.warmup_market_overview",
            lambda: ClosesFetchResult(closes={}, errors=[]),
        )

        resp = client.post("/api/v1/admin/data/import/stream?dataset=all")
        frames = _parse_sse(resp.text)
        events = [e for e, _ in frames]
        assert "error" not in events

        running_phases = [
            d["phase"]
            for e, d in frames
            if e == "progress" and d["status"] == "running"
        ]
        done_phases = [
            d["phase"]
            for e, d in frames
            if e == "progress" and d["status"] == "done"
        ]
        assert running_phases == [
            "turnover", "point", "stock", "global_assets",
            "us_macro", "cn_macro", "market_overview",
        ]
        assert done_phases == running_phases

        # done 帧:各阶段结果平铺 + 整体 status
        done_frames = [d for e, d in frames if e == "done"]
        assert len(done_frames) == 1
        assert set(done_frames[0].keys()) == {*running_phases, "status"}
        assert done_frames[0]["status"] == "success"

    def test_unknown_dataset_rejected_by_validation(self, client):
        resp = client.post("/api/v1/admin/data/import/stream?dataset=nope")
        assert resp.status_code == 422
        assert resp.json()["code"] == 1001
