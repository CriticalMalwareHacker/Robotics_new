"""Test cases for parking geometry + violation rules (synthetic, no hardware).

Table layout under test comes from backend/services/parking/config/slots.json:
A1/A2/B1/B2 open slots, Z1 restricted zone, all in cm.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.parking.analyzer import analyze_frame, load_slots
from backend.services.parking.models import Detection, ViolationType
from backend.services.parking.parking_geometry import (
    angle_diff_deg,
    apply_homography,
    build_homography,
    overlap_fraction,
    polygon_area,
    ViolationDebouncer,
)


@pytest.fixture(scope="module")
def slots():
    return {s.slot_id: s for s in load_slots()}


def det(vid, poly, angle=0.0, conf=0.9):
    return Detection(vehicle_id=vid, polygon=poly, angle_deg=angle, confidence=conf)


def test_polygon_area_and_overlap_basics(slots):
    a1 = slots["A1"].polygon
    assert polygon_area(a1) == pytest.approx(22 * 12)
    assert overlap_fraction(a1, a1) == pytest.approx(1.0)
    far = [[80, 60], [90, 60], [90, 65], [80, 65]]
    assert overlap_fraction(far, a1) == pytest.approx(0.0)
    half = [[5, 5], [16, 5], [16, 17], [5, 17]]  # left half of A1 (11x12 of 22x12)
    assert overlap_fraction(half, a1) == pytest.approx(1.0)  # car fully inside
    assert overlap_fraction(a1, half) == pytest.approx(0.5)  # half of car inside


def test_angle_diff_folds_at_90():
    assert angle_diff_deg(0, 0) == pytest.approx(0)
    assert angle_diff_deg(10, 0) == pytest.approx(10)
    assert angle_diff_deg(180, 0) == pytest.approx(0)  # same axis
    assert angle_diff_deg(170, 0) == pytest.approx(10)
    assert angle_diff_deg(45, 0) == pytest.approx(45)


def test_homography_roundtrip():
    src = [[100, 100], [500, 90], [510, 400], [90, 410]]  # px
    dst = [[0, 0], [100, 0], [100, 70], [0, 70]]  # cm
    h = build_homography(src, dst)
    got = apply_homography(h, src)
    import numpy as np

    assert np.allclose(np.asarray(got), np.asarray(dst), atol=1e-3)
    with pytest.raises(ValueError):
        build_homography(src[:3], dst[:3])


def test_legal_parking(slots):
    car = [[7, 7], [25, 7], [25, 15], [7, 15]]  # inside A1, aligned
    analysis = analyze_frame([det("C1", car)], list(slots.values()))
    assert analysis.vehicle_detected and analysis.parking_valid
    assert analysis.violation is None and analysis.slot == "A1"
    assert analysis.results[0].inside_fraction == pytest.approx(1.0)


def test_outside_slot(slots):
    car = [[70, 50], [85, 50], [85, 60], [70, 60]]  # open table, no slot
    analysis = analyze_frame([det("C1", car)], list(slots.values()))
    assert not analysis.parking_valid
    assert analysis.violation == ViolationType.OUTSIDE_SLOT
    assert analysis.slot is None


def test_straddling_two_slots(slots):
    # A1 spans x 5..27, A2 spans 30..52: car 20..35 overlaps both >= 15%
    car = [[20, 7], [35, 7], [35, 15], [20, 15]]
    analysis = analyze_frame([det("C1", car)], list(slots.values()))
    assert analysis.violation == ViolationType.STRADDLING
    assert analysis.slot in ("A1", "A2")


def test_wrong_orientation(slots):
    car = [[8, 6], [24, 6], [24, 16], [8, 16]]
    analysis = analyze_frame([det("C1", car, angle=45.0)], list(slots.values()))
    assert analysis.violation == ViolationType.WRONG_ORIENTATION
    assert analysis.results[0].angle_error_deg == pytest.approx(45.0)


def test_no_parking_zone(slots):
    car = [[62, 7], [80, 7], [80, 20], [62, 20]]  # inside restricted Z1
    analysis = analyze_frame([det("C1", car)], list(slots.values()))
    assert analysis.violation == ViolationType.NO_PARKING_ZONE
    assert analysis.slot == "Z1"


def test_empty_frame_is_valid():
    analysis = analyze_frame([], load_slots())
    assert not analysis.vehicle_detected and analysis.parking_valid
    assert analysis.results == []


def test_debouncer_needs_5_of_8():
    d = ViolationDebouncer(window=8, need=5)
    seq = [True, True, False, True, True, False, True, True]  # 6 of 8
    assert [d.update("C1", v) for v in seq][-1] is True
    d2 = ViolationDebouncer(window=8, need=5)
    assert [d2.update("C1", v) for v in [True] * 4 + [False] * 4][-1] is False
    with pytest.raises(ValueError):
        ViolationDebouncer(window=8, need=9)
