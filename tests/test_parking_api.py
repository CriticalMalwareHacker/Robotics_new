"""API tests for /api/parking/* (synthetic detections, no hardware).

Auth matrix: open when API_KEY env is empty (laptop dev); 401 without/wrong
key and 200 with the right one when API_KEY is set.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

client = TestClient(app)

LEGAL = {"vehicle_id": "C1", "polygon": [[7, 7], [25, 7], [25, 15], [7, 15]],
         "angle_deg": 0.0, "confidence": 0.92}
BAD = {"vehicle_id": "C1", "polygon": [[70, 50], [85, 50], [85, 60], [70, 60]],
       "angle_deg": 0.0, "confidence": 0.92}


def test_analyze_legal_and_violation_open_mode(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    ok = client.post("/api/parking/analyze", json={"detections": [LEGAL]})
    assert ok.status_code == 200
    body = ok.json()
    assert body["parking_valid"] is True and body["violation"] is None
    assert body["slot"] == "A1"

    bad = client.post("/api/parking/analyze", json={"detections": [BAD]})
    assert bad.status_code == 200
    bad_body = bad.json()
    assert bad_body["parking_valid"] is False
    assert bad_body["violation"] == "OUTSIDE_SLOT"
    assert bad_body["slot"] is None


def test_analyze_rejects_bad_input(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    resp = client.post("/api/parking/analyze", json={"detections": [
        {"vehicle_id": "C1", "polygon": [[0, 0]], "angle_deg": 0}]})  # <3 pts
    assert resp.status_code == 422


def test_status_shape(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    resp = client.get("/api/parking/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["monitor"] == "stopped" and body["slots_loaded"] == 5
    assert "last_analysis" in body


def test_api_key_enforced_when_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    assert client.get("/api/parking/status").status_code == 401
    assert client.post("/api/parking/analyze",
                       json={"detections": []}).status_code == 401
    wrong = client.get("/api/parking/status",
                       headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    good = client.get("/api/parking/status",
                      headers={"Authorization": "Bearer test-secret"})
    assert good.status_code == 200
    alt = client.post("/api/parking/analyze", json={"detections": []},
                      headers={"X-Api-Key": "test-secret"})
    assert alt.status_code == 200
