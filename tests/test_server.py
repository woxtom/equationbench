from __future__ import annotations

from fastapi.testclient import TestClient

from equationbench.server import create_app


def test_health_and_leaderboard_endpoints(tmp_path):
    app = create_app(tmp_path / "eqb.sqlite", dataset_path="datasets/equationbench-v1-dev", leaderboard_dir=tmp_path)
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    # No leaderboard directory has been built in tmp_path.
    assert client.get("/api/leaderboard").status_code == 404
