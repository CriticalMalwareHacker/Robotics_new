"""Tests for scannable QR ticket generation, annotated photo evidence snapshot,
database persistence, and citation history endpoints.
"""

from pathlib import Path
import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from backend.services.parking.models import Detection, Slot
from backend.services.parking.ticket import (
    build_ticket_image,
    generate_annotated_evidence,
    get_history,
    record_ticket,
)

client = TestClient(app)


def test_build_ticket_image_contains_scannable_qr(monkeypatch):
    """Verify that build_ticket_image generates a thermal receipt with a decodable QR code."""
    monkeypatch.setenv("TICKET_PORTAL_BASE_URL", "http://10.42.0.1:8000")
    img = build_ticket_image(
        number="T-261018-777",
        when="2026-10-18 18:00:00",
        plate="DL01XY9999",
        vehicle="car",
        slot="BAY-03",
        violation="STRADDLING",
    )

    assert img.width == 384
    assert img.height > 500

    np_img = np.array(img.convert("RGB"))
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(np_img)

    assert data == "http://10.42.0.1:8000/history?ticket=T-261018-777"


def test_generate_annotated_evidence_renders_bays_and_vehicle(tmp_path, monkeypatch):
    """Verify that generate_annotated_evidence creates an annotated snapshot."""
    monkeypatch.chdir(tmp_path)
    frame = np.full((480, 640, 3), 80, dtype=np.uint8)
    bays = [
        Slot(
            slot_id="BAY-01",
            polygon=[[40, 60], [200, 60], [200, 300], [40, 300]],
            polygon_px=[[40, 60], [200, 60], [200, 300], [40, 300]],
        ),
        Slot(
            slot_id="BAY-02",
            polygon=[[240, 60], [400, 60], [400, 300], [240, 300]],
            polygon_px=[[240, 60], [400, 60], [400, 300], [240, 300]],
        ),
    ]
    det = Detection(
        vehicle_id="test_car",
        confidence=0.95,
        bbox_xyxy=[160, 100, 320, 260],
        polygon=[[160, 100], [320, 100], [320, 260], [160, 260]],
        polygon_px=[[160, 100], [320, 100], [320, 260], [160, 260]],
        angle_deg=15.0,
    )

    url = generate_annotated_evidence(
        frame_bgr=frame,
        bays=bays,
        vehicle_det=det,
        slot_id="BAY-01",
        violation_name="BAY STRADDLING",
        plate="DL01XY9999",
        ticket_number="T-261018-777",
    )

    assert url.startswith("/generated_labels/evidence_")
    saved_file = tmp_path / url.lstrip("/")
    assert saved_file.exists()
    assert saved_file.stat().st_size > 1000

    read_back = cv2.imread(str(saved_file))
    assert read_back is not None
    assert read_back.shape == (480, 640, 3)


def test_record_ticket_and_history_persistence():
    """Verify that record_ticket dual-persists and get_history returns it."""
    test_ticket = {
        "number": "T-TEST-PERSIST-01",
        "plate": "KA01ZZ0001",
        "vehicle": "sedan",
        "slot": "BAY-02",
        "violation": "OUTSIDE_SLOT",
        "status": "printed",
        "message": "Double parked over white lines",
        "image_url": "/generated_labels/ticket_T-TEST-PERSIST-01.png",
        "evidence_url": "/generated_labels/evidence_T-TEST-PERSIST-01.jpg",
    }

    record_ticket(test_ticket)
    history = get_history()
    match = next((t for t in history if t.get("number") == "T-TEST-PERSIST-01"), None)
    assert match is not None
    assert match["plate"] == "KA01ZZ0001"
    assert match["slot"] == "BAY-02"
    assert match["evidence_url"] == "/generated_labels/evidence_T-TEST-PERSIST-01.jpg"


def test_api_citation_lookup_and_history_portal():
    """Verify GET /api/ticket/{number} and direct SPA GET /history."""
    test_ticket = {
        "number": "T-API-LOOKUP-99",
        "plate": "MH04AB5678",
        "vehicle": "car",
        "slot": "BAY-05",
        "violation": "NO_PARKING_ZONE",
        "status": "printed",
        "image_url": "/generated_labels/ticket_T-API-LOOKUP-99.png",
        "evidence_url": "/generated_labels/evidence_T-API-LOOKUP-99.jpg",
    }
    record_ticket(test_ticket)

    # 1. API Lookup
    res = client.get("/api/ticket/T-API-LOOKUP-99")
    assert res.status_code == 200
    data = res.json()
    assert data["number"] == "T-API-LOOKUP-99"
    assert data["plate"] == "MH04AB5678"
    assert data["evidence_url"] == "/generated_labels/evidence_T-API-LOOKUP-99.jpg"

    # Non-existent ticket returns 404
    missing_res = client.get("/api/ticket/T-DOES-NOT-EXIST")
    assert missing_res.status_code == 404

    # 2. History Portal route returns index.html
    hist_res = client.get("/history")
    assert hist_res.status_code == 200
    assert "text/html" in hist_res.headers.get("content-type", "")
