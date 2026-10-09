"""Tests for HUD backend: combined state, mock robot, ticket, stream chunk."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from backend.services.parking import events  # noqa: E402

client = TestClient(app)


def test_hud_state_shape(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    events.clear()
    resp = client.get("/api/hud/state")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"frame", "robot", "parking", "devices", "ticket", "events"}
    assert body["devices"]["backend"] == "ok"
    assert body["robot"]["state"] in ("IDLE", "MONITORING", "PATROLLING", "ESTOP")
    assert isinstance(body["parking"]["slots"], list)
    assert body["events"] == []


def test_hud_slot_boxes_scale_inside_native_camera_frame(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(
        "app.services.camera.camera_manager.get_frame_meta",
        lambda: {"id": 1, "width": 640, "height": 480,
                 "available": True, "brightness": 180.0},
    )
    body = client.get("/api/hud/state").json()
    assert body["frame"]["width"] == 640
    assert body["frame"]["height"] == 480
    assert body["parking"]["slots"]
    for slot in body["parking"]["slots"]:
        for x, y in slot["polygon_px"]:
            assert 0 <= x <= 640
            assert 0 <= y <= 480


def test_robot_command_validation_and_estop_flow(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ROBOT_MODE", "mock")
    assert client.post("/api/robot/estop/clear").status_code == 200

    bad = client.post("/api/robot/command",
                      json={"command": "X", "speed": 120, "duration_ms": 200})
    assert bad.status_code == 422
    too_fast = client.post("/api/robot/command",
                           json={"command": "F", "speed": 999, "duration_ms": 200})
    assert too_fast.status_code == 422

    assert client.post("/api/robot/command",
                       json={"command": "F", "speed": 120,
                             "duration_ms": 200}).status_code == 200

    assert client.post("/api/robot/estop").status_code == 200
    assert client.get("/api/robot/status").json()["estop"] is True
    blocked = client.post("/api/robot/command",
                          json={"command": "S", "speed": 0, "duration_ms": 0})
    assert blocked.status_code == 409
    assert client.post("/api/robot/estop/clear").status_code == 200
    assert client.get("/api/robot/status").json()["estop"] is False


def test_robot_auto_start_stop(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("ROBOT_MODE", "mock")
    monkeypatch.setattr("app.services.camera.camera_manager.get_latest_jpeg",
                        lambda: None)
    client.post("/api/robot/estop/clear")
    assert client.post("/api/robot/auto/start").status_code == 200
    assert client.get("/api/robot/status").json()["mode"] == "auto"
    assert client.post("/api/robot/auto/stop").status_code == 200
    assert client.get("/api/robot/status").json()["mode"] == "idle"


def test_ticket_test_print_uses_simulated_printer(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # keep generated_labels out of the repo
    # transport stubbed: USB bus scans are slow on hardware-less laptops;
    # encoding + route logic is what this test owns (see test_printer.py).
    monkeypatch.setattr("app.services.printer.print_label",
                        lambda image: (True, "Simulated print (test)"))
    resp = client.post("/api/ticket/test-print")
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "ok"  # HARDWARE_MODE=pc -> simulated print
    assert body["status"] == "printed"
    assert body["number"].startswith("T-")
    assert (tmp_path / "generated_labels").exists()
    pngs = list((tmp_path / "generated_labels").glob("ticket_*.png"))
    assert len(pngs) == 1 and pngs[0].stat().st_size > 1000


def test_stream_headers_without_consuming_body():
    import asyncio

    from app.api.parking_routes import stream

    resp = stream()
    assert resp.status_code == 200
    assert resp.media_type.startswith("multipart/x-mixed-replace")

    async def first_chunk():
        async for chunk in resp.body_iterator:
            return chunk

    first = asyncio.run(first_chunk())
    assert first.startswith(b"--frame\r\nContent-Type: image/jpeg")
