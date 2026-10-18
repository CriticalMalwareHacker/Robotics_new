"""Tests for the high-accuracy offline license plate reader (ANPR)."""

import numpy as np
import pytest

from backend.services.parking.models import Detection
from backend.services.parking.plate_reader import (
    _clean_and_repair_plate_candidate,
    _extract_ocr_items,
    _format_plate_string,
    _order_quad_clockwise,
    _PLATE_PATTERN,
    read_vehicle_plates,
)


def test_plate_pattern_matches_tabletop_and_standard_plates():
    """Verify that regex matches both tabletop demo plates and standard Indian plates."""
    samples = {
        "MHEF4752": "MHEF4752",
        "MHHR1058": "MHHR1058",
        "MH EF 4752": "MHEF4752",
        "MH HR 1058": "MHHR1058",
        "MH12DE1433": "MH12DE1433",
        "KA03AB1234": "KA03AB1234",
        "DL02CD5678": "DL02CD5678",
        "22BH1234AA": "22BH1234AA",
    }
    for raw, expected in samples.items():
        clean = raw.replace(" ", "")
        match = _PLATE_PATTERN.search(clean)
        assert match is not None, f"Failed to match: {raw}"
        assert match.group(0) == expected


def test_format_plate_string():
    """Verify plate formatting adds standard readable spacing."""
    assert _format_plate_string("MHEF4752") == "MH EF 4752"
    assert _format_plate_string("MHHR1058") == "MH HR 1058"
    assert _format_plate_string("MH12DE1234") == "MH 12 DE 1234"
    assert _format_plate_string("KA03AB1234") == "KA 03 AB 1234"


def test_clean_and_repair_plate_candidate():
    """Verify candidate repair and fuzzy match against known demo plates."""
    assert _clean_and_repair_plate_candidate("MHEF4752") == "MHEF4752"
    assert _clean_and_repair_plate_candidate("MHHR1058") == "MHHR1058"
    # 1-char OCR confusion tolerance
    assert _clean_and_repair_plate_candidate("MMEF4752") == "MHEF4752"


def test_universal_ocr_unpacker():
    """Verify extraction across RapidOCR v1, v2, v3 and Tesseract output structures."""
    # RapidOCR v3 Dataclass
    class MockV3:
        txts = ["MH EF 4752"]
        scores = [0.93]

    assert _extract_ocr_items(MockV3()) == [("MH EF 4752", 0.93)]

    # RapidOCR standard tuple (result_list, elapse_list)
    v1_tuple = ([([[0, 0], [10, 0], [10, 5], [0, 5]], "MH HR 1058", 0.91)], [0.01])
    assert _extract_ocr_items(v1_tuple) == [("MH HR 1058", 0.91)]

    # Direct list format
    list_fmt = [([[0, 0], [10, 0], [10, 5], [0, 5]], "KA03AB1234", 0.95)]
    assert _extract_ocr_items(list_fmt) == [("KA03AB1234", 0.95)]

    # String format (pytesseract)
    str_fmt = "MH EF 4752\n"
    assert _extract_ocr_items(str_fmt) == [("MH EF 4752", 0.85)]


def test_order_quad_clockwise():
    """Verify clockwise ordering returns [TL, TR, BR, BL]."""
    pts = np.array([[200, 400], [100, 100], [100, 400], [200, 100]], dtype=np.float32)
    ordered = _order_quad_clockwise(pts)
    assert np.allclose(ordered[0], [100, 100])  # TL
    assert np.allclose(ordered[1], [200, 100])  # TR
    assert np.allclose(ordered[2], [200, 400])  # BR
    assert np.allclose(ordered[3], [100, 400])  # BL


def test_read_vehicle_plates_populates_detection(monkeypatch):
    """Verify read_vehicle_plates extracts and populates plate_hint on Detection."""
    class MockEngine:
        def __call__(self, img):
            return ([([[0, 0], [10, 0], [10, 5], [0, 5]], "MH EF 4752", 0.95)], [0.01])

    monkeypatch.setattr("backend.services.parking.plate_reader._get_engine", lambda: MockEngine())

    frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    det = Detection(
        vehicle_id="CAR-01",
        confidence=0.95,
        polygon=[[100, 100], [200, 100], [200, 300], [100, 300]],
        polygon_px=[[100, 100], [200, 100], [200, 300], [100, 300]],
        angle_deg=90.0,
    )

    results = read_vehicle_plates(frame, [det])
    assert len(results) == 1
    assert results[0].plate_hint == "MH EF 4752"
    assert results[0].plate_conf is not None and results[0].plate_conf >= 0.90
