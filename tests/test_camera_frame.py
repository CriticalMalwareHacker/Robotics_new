"""Phase 1 tests (mock-only, no hardware): /api/camera/frame contract + probe fallback."""

import sys
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.services.camera import CameraManager  # noqa: E402


def _fake_jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    img = np.full((height, width, 3), 128, dtype=np.uint8)
    cv2.putText(img, "TEST", (20, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    ok, jpeg = cv2.imencode(".jpg", img)
    assert ok
    return bytes(jpeg.tobytes())


def test_camera_frame_returns_jpeg_when_camera_ready(monkeypatch):
    payload = _fake_jpeg_bytes()
    monkeypatch.setattr(
        "app.services.camera.camera_manager.get_latest_jpeg", lambda: payload
    )
    client = TestClient(app)
    resp = client.get("/api/camera/frame")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:2] == b"\xff\xd8"  # real JPEG magic
    arr = np.frombuffer(resp.content, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert frame is not None
    assert frame.shape[1] == 320 and frame.shape[0] == 240


def test_camera_frame_503_when_camera_not_ready(monkeypatch):
    monkeypatch.setattr(
        "app.services.camera.camera_manager.get_latest_jpeg", lambda: None
    )
    client = TestClient(app)
    resp = client.get("/api/camera/frame")
    assert resp.status_code == 503


def test_probe_mock_frame_generates_synthetic_jpeg(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import test_camera as probe

    frame = probe.make_mock_frame_bgr(640, 480)
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    out = tmp_path / "mock.jpg"
    probe.save_bgr_as_jpeg(frame, out)
    assert out.exists() and out.stat().st_size > 1000
    raw = out.read_bytes()
    assert raw[:2] == b"\xff\xd8"


def test_windows_camera_selection_chooses_brightest_and_caches(monkeypatch):
    class FakeCapture:
        def __init__(self, index):
            self.index = index
            self.released = False

        def isOpened(self):
            return self.index in (0, 1)

        def read(self):
            if self.index == 0:
                return True, np.zeros((8, 8, 3), dtype=np.uint8)
            return True, np.full((8, 8, 3), 180, dtype=np.uint8)

        def release(self):
            self.released = True

    opened = []

    def fake_video_capture(index):
        cap = FakeCapture(index)
        opened.append(cap)
        return cap

    monkeypatch.delenv("CAMERA_INDEX", raising=False)
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(cv2, "VideoCapture", fake_video_capture)

    manager = CameraManager()
    assert manager._get_device_index() == 1
    assert manager._get_device_index() == 1
    assert len(opened) == 3  # probe each candidate once; second call is cached
    assert all(cap.released for cap in opened)
