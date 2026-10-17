import cv2
import numpy as np
import pytest

from backend.services.parking.dynamic_detector import (
    detect_marker_lines_and_bays,
    detect_vehicle_cards,
    analyze_dynamic_parking,
)
from backend.services.parking.models import ViolationType


def test_detect_marker_lines_and_bays_synthetic():
    # 640x480 white canvas
    img = np.full((480, 640, 3), 245, dtype=np.uint8)

    # Draw two parallel vertical-ish black marker lines (representing a parking bay)
    # Line 1: x ~ 200, y: 180 to 460
    cv2.line(img, (200, 180), (205, 460), (20, 20, 20), 4)
    # Line 2: x ~ 360, y: 180 to 460
    cv2.line(img, (360, 180), (365, 460), (20, 20, 20), 4)

    bays, lines = detect_marker_lines_and_bays(img)
    assert len(lines) >= 2
    assert len(bays) >= 1
    bay = bays[0]
    assert bay.slot_id == "BAY-1"
    assert len(bay.polygon_px) == 4


def test_detect_vehicle_cards_synthetic():
    # 640x480 white canvas
    img = np.full((480, 640, 3), 245, dtype=np.uint8)

    # Draw a saturated red rectangular card on the floor: center (280, 320), size (80, 140)
    # in BGR, saturated red is (0, 0, 220)
    cv2.rectangle(img, (240, 250), (320, 390), (10, 10, 230), -1)

    dets = detect_vehicle_cards(img)
    assert len(dets) >= 1
    car = dets[0]
    assert car.vehicle_id == "CAR-01"
    assert len(car.polygon_px) == 4
    assert car.confidence >= 0.85


def test_dynamic_parking_violation_rules():
    # 640x480 white canvas
    img = np.full((480, 640, 3), 245, dtype=np.uint8)

    # Draw two black lines
    cv2.line(img, (180, 180), (180, 460), (20, 20, 20), 4)
    cv2.line(img, (340, 180), (340, 460), (20, 20, 20), 4)

    bays, lines = detect_marker_lines_and_bays(img)
    assert len(bays) >= 1

    # 1. Car centered neatly between the lines -> LEGAL
    legal_img = img.copy()
    cv2.rectangle(legal_img, (220, 260), (300, 380), (10, 10, 230), -1)
    legal_dets = detect_vehicle_cards(legal_img)
    assert len(legal_dets) >= 1
    analysis_legal = analyze_dynamic_parking(legal_dets, bays, lines)
    assert analysis_legal.parking_valid is True
    assert analysis_legal.results[0].violation == ViolationType.LEGAL

    # 2. Car crossing the left line (x=180) -> STRADDLING
    straddle_img = img.copy()
    cv2.rectangle(straddle_img, (150, 260), (230, 380), (10, 10, 230), -1)
    straddle_dets = detect_vehicle_cards(straddle_img)
    assert len(straddle_dets) >= 1
    analysis_straddle = analyze_dynamic_parking(straddle_dets, bays, lines)
    assert analysis_straddle.parking_valid is False
    assert analysis_straddle.results[0].violation == ViolationType.STRADDLING
