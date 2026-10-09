"""Detector tests on the real mat frame + variant results table (no motors).

Golden fixture: tests/data/mat_baseline.jpg (1280x720 Hikvision, top-down,
3 paper cars on hand-drawn 3-bay mat). Ground truth: all 3 LEGAL.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from backend.services.parking import monitor  # noqa: E402
from backend.services.parking.analyzer import analyze_frame  # noqa: E402
from backend.services.parking.models import Detection, Slot, ViolationType  # noqa: E402
from backend.services.parking.vehicle_detector import ClassicalDetector  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "mat_baseline.jpg"

# This image was captured with the original 1280x720 camera view. Keep its
# calibration local to the fixture so updating the live camera calibration
# does not silently change the golden detector test.
BASELINE_H = np.asarray([
    [0.05618514628402719, 0.006521490193681729, -10.51715707004134],
    [-0.0029376735757340668, 0.08015652185217241, -7.902341918724642],
    [-9.2409997729913e-05, 1.791246477534928e-05, 1.0],
], dtype=np.float64)
BASELINE_ROI = [[175.0, 105.0], [1130.0, 140.0],
                [1085.0, 650.0], [110.0, 665.0]]


def baseline_slots():
    return [
        Slot(slot_id="A1", polygon=[[0.0, 0.0], [16.2, 0.58],
                                     [18.55, 44.59], [0.0, 45.0]],
             angle_deg=90.0, restricted=False),
        Slot(slot_id="A2", polygon=[[16.2, 0.58], [36.22, 0.44],
                                     [38.83, 44.75], [18.55, 44.59]],
             angle_deg=90.0, restricted=False),
        Slot(slot_id="A3", polygon=[[36.22, 0.44], [60.0, 0.0],
                                     [60.0, 45.0], [38.83, 44.75]],
             angle_deg=90.0, restricted=False),
    ]


def detector():
    return ClassicalDetector(BASELINE_H, roi_px=BASELINE_ROI,
                             calib_size=(1280, 720))


def test_real_frame_finds_three_legal_cars():
    img = cv2.imread(str(DATA))
    assert img is not None
    dets = detector().detect(img)
    assert len(dets) == 3
    assert [d.vehicle_id for d in dets] == ["CAR-01", "CAR-02", "CAR-03"]
    analysis = analyze_frame(dets, baseline_slots())
    assert analysis.parking_valid and analysis.violation is None
    by_slot = {r.slot_id: r for r in analysis.results}
    assert set(by_slot) == {"A1", "A2", "A3"}
    assert all(r.violation == ViolationType.LEGAL for r in by_slot.values())
    tilted = by_slot["A2"]  # hand-placed crooked paper car
    assert 5.0 < tilted.angle_error_deg < 25.0


def test_empty_frame_finds_nothing():
    blank = np.full((720, 1280, 3), 255, dtype=np.uint8)
    assert detector().detect(blank) == []


def _shift(poly, dx, dy):
    return [[x + dx, y + dy] for x, y in poly]


def test_variant_results_table():
    """Brief gate: one frame, five placements -> correct decisions."""
    img = cv2.imread(str(DATA))
    slots = baseline_slots()
    base = {d.vehicle_id: d for d in detector().detect(img)}

    a1 = next(s for s in slots if s.slot_id == "A1")
    a2 = next(s for s in slots if s.slot_id == "A2")
    boundary_x = (max(p[0] for p in a1.polygon)
                  + min(p[0] for p in a2.polygon)) / 2
    cy = sum(p[1] for p in a1.polygon) / len(a1.polygon)
    straddler = Detection(vehicle_id="X", confidence=0.9, angle_deg=90.0,
                          polygon=[[boundary_x - 7.5, cy - 6],
                                   [boundary_x + 7.5, cy - 6],
                                   [boundary_x + 7.5, cy + 6],
                                   [boundary_x - 7.5, cy + 6]])
    car = base["CAR-01"]
    rows = {
        "valid   (as parked)": analyze_frame([car], slots),
        "outside (shifted off mat)": analyze_frame(
            [car.model_copy(update={"polygon": _shift(car.polygon, 40, 30)})], slots),
        "straddle (on A1/A2 line)": analyze_frame([straddler], slots),
        "rotated (45 deg)": analyze_frame(
            [car.model_copy(update={"angle_deg": 45.0})], slots),
        "empty   (no cars)": analyze_frame([], slots),
    }
    assert rows["valid   (as parked)"].parking_valid
    assert rows["outside (shifted off mat)"].violation == ViolationType.OUTSIDE_SLOT
    assert rows["straddle (on A1/A2 line)"].violation == ViolationType.STRADDLING
    assert rows["rotated (45 deg)"].violation == ViolationType.WRONG_ORIENTATION
    assert rows["empty   (no cars)"].parking_valid
    table = "\n".join(f"{name}: valid={a.parking_valid} "
                      f"violation={a.violation.value if a.violation else None}"
                      for name, a in rows.items())
    print("\n" + table)


def test_monitor_start_stop_with_synthetic_provider(monkeypatch):
    import time
    monkeypatch.delenv("API_KEY", raising=False)
    # fast deterministic ticks: no camera reads in CI
    monkeypatch.setattr("app.services.camera.camera_manager.get_latest_jpeg",
                        lambda: None)
    client = TestClient(app)
    assert client.post("/api/parking/monitor/start").status_code == 200
    assert client.post("/api/parking/monitor/start").status_code == 200  # idempotent
    time.sleep(0.4)
    body = client.get("/api/parking/status").json()
    assert body["monitor"] == "running"
    assert body["last_analysis"] is not None
    assert client.post("/api/parking/monitor/stop").status_code == 200
    assert client.get("/api/parking/status").json()["monitor"] == "stopped"
    monitor.stop()


def test_parking_frame_route(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    jpeg = DATA.read_bytes()
    monkeypatch.setattr("app.services.camera.camera_manager.get_latest_jpeg",
                        lambda: jpeg)
    resp = TestClient(app).get("/api/parking/frame")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:2] == b"\xff\xd8"

    monkeypatch.setattr("app.services.camera.camera_manager.get_latest_jpeg",
                        lambda: None)
    assert TestClient(app).get("/api/parking/frame").status_code == 503
