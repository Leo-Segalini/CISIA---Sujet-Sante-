from __future__ import annotations

from fastapi.testclient import TestClient

from src.web.app import app


def test_ml_status_endpoint():
    client = TestClient(app)
    r = client.get("/api/ml/status")
    assert r.status_code == 200
    body = r.json()
    assert "retrain" in body
    assert "registry" in body
