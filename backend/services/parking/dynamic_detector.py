"""Dynamic Computer Vision Pipeline for ParkSensei.

Detects:
1. N straight black marker lines on the floor and clusters them into dynamic parking bays.
2. Rectangular colored cards (or box cars) placed as vehicles.
3. Evaluates parking violations dynamically relative to the detected lines:
   - STRADDLING: Vehicle overlaps or crosses a parking divider line.
   - WRONG_ORIENTATION: Vehicle angle deviates from parking bay lines by > 20 deg.
   - OUTSIDE_SLOT: Vehicle is outside detected parking bays.
   - LEGAL: Vehicle is neatly parked inside a bay parallel to marker lines.
"""

from __future__ import annotations

import logging
import math
from typing import Sequence

import cv2
import numpy as np

from .models import Detection, ParkingAnalysis, Slot, SlotResult, ViolationType

logger = logging.getLogger(__name__)

# Line detection thresholds
MIN_LINE_LEN_PX = 50
MAX_LINE_GAP_PX = 30
MAX_LINE_SLOPE_DIFF_DEG = 12.0
MAX_LINE_DIST_PX = 40.0

# Vehicle card detection thresholds
MIN_CARD_AREA_PX = 2500
MAX_CARD_AREA_PX = 450000
MIN_ASPECT_RATIO = 1.1
MAX_ASPECT_RATIO = 4.5

# Orientation tolerance
MAX_ANGLE_ERROR_DEG = 20.0


def _line_angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """Line orientation folded to [0, 180)."""
    dx = x2 - x1
    dy = y2 - y1
    ang = float(math.degrees(math.atan2(dy, dx))) % 180.0
    return ang


def _line_distance(p1: tuple[float, float], p2: tuple[float, float], pt: tuple[float, float]) -> float:
    """Perpendicular distance from point `pt` to line segment `p1`-`p2`."""
    x0, y0 = pt
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm


def detect_marker_lines_and_bays(frame_bgr: np.ndarray) -> tuple[list[Slot], list[tuple[int, int, int, int]]]:
    """Detect black marker lines on the floor ROI and group parallel lines into parking bays."""
    if frame_bgr is None or frame_bgr.size == 0:
        return [], []

    fh, fw = frame_bgr.shape[:2]
    # Restrict to floor ROI (lower 70% of the image)
    roi_top = int(fh * 0.30)
    roi = frame_bgr[roi_top:fh, 0:fw]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detect black marker lines: black strokes have lower intensity than the floor.
    # Adaptive inverse threshold isolates dark marker lines.
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=21, C=10
    )

    # Clean speckles while keeping line strokes intact
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    clean_mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    lines_p = cv2.HoughLinesP(
        clean_mask, rho=1, theta=np.pi / 180,
        threshold=35, minLineLength=MIN_LINE_LEN_PX, maxLineGap=MAX_LINE_GAP_PX
    )

    if lines_p is None:
        return [], []

    raw_lines: list[tuple[int, int, int, int, float]] = []
    for line in lines_p:
        vals = np.asarray(line).reshape(-1)
        if len(vals) < 4:
            continue
        x1, y1, x2, y2 = int(vals[0]), int(vals[1]), int(vals[2]), int(vals[3])
        # Map y coordinate back to full frame
        y1_full = y1 + roi_top
        y2_full = y2 + roi_top
        ang = _line_angle_deg(x1, y1_full, x2, y2_full)

        # Reject purely horizontal lines (within 15 deg of 0 or 180) to ignore baseboards/floor joints
        if ang < 15.0 or ang > 165.0:
            continue

        raw_lines.append((x1, y1_full, x2, y2_full, ang))

    if not raw_lines:
        return [], []

    # Merge collinear and close lines
    merged_lines: list[tuple[int, int, int, int, float]] = []
    used = set()

    for i, l1 in enumerate(raw_lines):
        if i in used:
            continue
        x1_a, y1_a, x2_a, y2_a, ang_a = l1
        cluster = [(x1_a, y1_a), (x2_a, y2_a)]
        used.add(i)

        for j, l2 in enumerate(raw_lines[i + 1:], start=i + 1):
            if j in used:
                continue
            x1_b, y1_b, x2_b, y2_b, ang_b = l2
            d_ang = abs(ang_a - ang_b)
            if d_ang > 90.0:
                d_ang = 180.0 - d_ang

            if d_ang < MAX_LINE_SLOPE_DIFF_DEG:
                dist1 = _line_distance((x1_a, y1_a), (x2_a, y2_a), (x1_b, y1_b))
                dist2 = _line_distance((x1_a, y1_a), (x2_a, y2_a), (x2_b, y2_b))
                if min(dist1, dist2) < MAX_LINE_DIST_PX:
                    cluster.extend([(x1_b, y1_b), (x2_b, y2_b)])
                    used.add(j)

        # Fit principal line to cluster
        pts = np.array(cluster, dtype=np.float32)
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy, x0, y0 = float(vx[0]), float(vy[0]), float(x0[0]), float(y0[0])

        min_y = float(pts[:, 1].min())
        max_y = float(pts[:, 1].max())
        if abs(vy) > 1e-4:
            x_top = int(round(x0 + (min_y - y0) * (vx / vy)))
            x_bot = int(round(x0 + (max_y - y0) * (vx / vy)))
            y_top = int(round(min_y))
            y_bot = int(round(max_y))
            merged_lines.append((x_top, y_top, x_bot, y_bot, _line_angle_deg(x_top, y_top, x_bot, y_bot)))

    # Sort lines left-to-right by their bottom x coordinate
    merged_lines.sort(key=lambda l: (l[0] + l[2]) / 2)

    # Form dynamic parking bays between adjacent pairs of marker lines
    bays: list[Slot] = []
    for idx in range(len(merged_lines) - 1):
        l1 = merged_lines[idx]
        l2 = merged_lines[idx + 1]

        # Calculate horizontal distance between lines
        cx1 = (l1[0] + l1[2]) / 2
        cx2 = (l2[0] + l2[2]) / 2
        dx = abs(cx2 - cx1)

        # Realistic slot width: between 40px and 550px depending on resolution
        if 40 < dx < 600:
            bay_poly = [
                [float(l1[0]), float(l1[1])],
                [float(l2[0]), float(l2[1])],
                [float(l2[2]), float(l2[3])],
                [float(l1[2]), float(l1[3])],
            ]
            bay_poly_px = [
                [int(round(l1[0])), int(round(l1[1]))],
                [int(round(l2[0])), int(round(l2[1]))],
                [int(round(l2[2])), int(round(l2[3]))],
                [int(round(l1[2])), int(round(l1[3]))],
            ]
            avg_ang = round((l1[4] + l2[4]) / 2, 1)
            bays.append(
                Slot(
                    slot_id=f"BAY-{len(bays) + 1}",
                    polygon=bay_poly,
                    angle_deg=avg_ang,
                    restricted=False,
                    polygon_px=bay_poly_px,
                )
            )

    line_segments = [(l[0], l[1], l[2], l[3]) for l in merged_lines]
    return bays, line_segments


def detect_vehicle_cards(frame_bgr: np.ndarray) -> list[Detection]:
    """Detect colored rectangular cards (or box cars) on the ground floor."""
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    fh, fw = frame_bgr.shape[:2]
    roi_top = int(fh * 0.25)
    roi = frame_bgr[roi_top:fh, 0:fw]

    # Convert to HSV to extract colored cards (red, blue, yellow, green, orange, magenta)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Color saturation mask: colorful cards have higher saturation than neutral floors
    sat_mask = cv2.inRange(hsv, (0, 50, 40), (180, 255, 255))

    # Also detect cards with strong edges (e.g. white cards with dark borders)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 150)
    edges_dilated = cv2.dilate(edges, np.ones((5, 5), np.uint8))

    # Combined candidate mask
    combined = cv2.bitwise_or(sat_mask, edges_dilated)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    mask = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, np.ndarray, float]] = []
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if not (MIN_CARD_AREA_PX <= area <= MAX_CARD_AREA_PX):
            continue

        rect = cv2.minAreaRect(cnt)
        (cx, cy), (w, h), angle = rect
        if w < 20 or h < 20:
            continue

        aspect = max(w, h) / min(w, h)
        if not (MIN_ASPECT_RATIO <= aspect <= MAX_ASPECT_RATIO):
            continue

        # Map back to full image coordinates
        box = cv2.boxPoints(rect)
        box[:, 1] += roi_top

        # Find long edge orientation in [0, 180)
        best_len, best_ang = 0.0, 0.0
        for i in range(4):
            pt1 = box[i]
            pt2 = box[(i + 1) % 4]
            ln = float(np.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1]))
            if ln > best_len:
                best_len = ln
                best_ang = float(math.degrees(math.atan2(pt2[1] - pt1[1], pt2[0] - pt1[0]))) % 180.0

        candidates.append((cx, box, best_ang))

    # Sort left-to-right for consistent car numbering
    candidates.sort(key=lambda c: c[0])

    detections: list[Detection] = []
    for i, (_, box, ang) in enumerate(candidates, start=1):
        poly_list = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in box]
        poly_px = [[int(round(p[0])), int(round(p[1]))] for p in box]

        detections.append(
            Detection(
                vehicle_id=f"CAR-{i:02d}",
                polygon=poly_list,
                angle_deg=round(ang, 1),
                confidence=0.92,
                polygon_px=poly_px,
            )
        )

    return detections


def analyze_dynamic_parking(
    detections: list[Detection],
    bays: list[Slot],
    lines: list[tuple[int, int, int, int]]
) -> ParkingAnalysis:
    """Evaluate vehicle violations dynamically relative to detected parking lines and bays."""
    if not detections:
        return ParkingAnalysis(
            vehicle_detected=False,
            parking_valid=True,
            violation=None,
            confidence=0.0,
            results=[],
        )

    results: list[SlotResult] = []

    for vehicle in detections:
        car_poly = np.asarray(vehicle.polygon, dtype=np.float32)
        car_area = float(abs(cv2.contourArea(car_poly)))
        if car_area <= 0:
            car_area = 1.0

        # Check line crossing (straddling) against all detected marker lines
        is_straddling = False
        car_min_y = min(p[1] for p in vehicle.polygon)
        car_max_y = max(p[1] for p in vehicle.polygon)

        for lx1, ly1, lx2, ly2 in lines:
            line_seg = ((float(lx1), float(ly1)), (float(lx2), float(ly2)))
            line_min_y = min(ly1, ly2)
            line_max_y = max(ly1, ly2)

            # Check vertical overlap
            if car_max_y < line_min_y or car_min_y > line_max_y:
                continue

            dx = float(lx2 - lx1)
            dy = float(ly2 - ly1)
            side_signs = []
            close_corners = 0

            for pt in vehicle.polygon:
                d = _line_distance(line_seg[0], line_seg[1], (pt[0], pt[1]))
                if d < 16.0:
                    close_corners += 1
                cross = dx * (pt[1] - ly1) - dy * (pt[0] - lx1)
                side_signs.append(1 if cross > 40 else (-1 if cross < -40 else 0))

            has_pos = any(s == 1 for s in side_signs)
            has_neg = any(s == -1 for s in side_signs)

            if (has_pos and has_neg) or close_corners >= 2:
                is_straddling = True
                break

        if is_straddling:
            results.append(
                SlotResult(
                    vehicle_id=vehicle.vehicle_id,
                    slot_id=None,
                    violation=ViolationType.STRADDLING,
                    confidence=vehicle.confidence,
                    inside_fraction=0.5,
                    angle_error_deg=0.0,
                )
            )
            continue

        # Check overlap with dynamic bays
        best_bay: Slot | None = None
        best_overlap_frac = 0.0

        for bay in bays:
            bay_poly = np.asarray(bay.polygon, dtype=np.float32)
            try:
                _ret, inter = cv2.intersectConvexConvex(car_poly, bay_poly)
                if inter is not None and len(inter) > 0:
                    inter_area = float(abs(cv2.contourArea(inter)))
                    frac = min(1.0, inter_area / car_area)
                    if frac > best_overlap_frac:
                        best_overlap_frac = frac
                        best_bay = bay
            except cv2.error:
                continue

        # If straddling multiple bays
        bay_overlaps = []
        for bay in bays:
            bay_poly = np.asarray(bay.polygon, dtype=np.float32)
            try:
                _ret, inter = cv2.intersectConvexConvex(car_poly, bay_poly)
                if inter is not None and len(inter) > 0:
                    frac = float(abs(cv2.contourArea(inter))) / car_area
                    if frac >= 0.15:
                        bay_overlaps.append((bay, frac))
            except cv2.error:
                continue

        if len(bay_overlaps) >= 2:
            results.append(
                SlotResult(
                    vehicle_id=vehicle.vehicle_id,
                    slot_id=bay_overlaps[0][0].slot_id,
                    violation=ViolationType.STRADDLING,
                    confidence=vehicle.confidence,
                    inside_fraction=bay_overlaps[0][1],
                    angle_error_deg=0.0,
                )
            )
            continue

        # If not inside any bay
        if best_bay is None or best_overlap_frac < 0.70:
            results.append(
                SlotResult(
                    vehicle_id=vehicle.vehicle_id,
                    slot_id=best_bay.slot_id if best_bay else None,
                    violation=ViolationType.OUTSIDE_SLOT,
                    confidence=vehicle.confidence,
                    inside_fraction=best_overlap_frac,
                    angle_error_deg=0.0,
                )
            )
            continue

        # Check angle alignment with the parking bay
        d_ang = abs(vehicle.angle_deg - best_bay.angle_deg) % 180.0
        if d_ang > 90.0:
            d_ang = 180.0 - d_ang

        if d_ang > MAX_ANGLE_ERROR_DEG:
            results.append(
                SlotResult(
                    vehicle_id=vehicle.vehicle_id,
                    slot_id=best_bay.slot_id,
                    violation=ViolationType.WRONG_ORIENTATION,
                    confidence=vehicle.confidence,
                    inside_fraction=best_overlap_frac,
                    angle_error_deg=round(d_ang, 1),
                )
            )
            continue

        # If clean and aligned inside bay
        results.append(
            SlotResult(
                vehicle_id=vehicle.vehicle_id,
                slot_id=best_bay.slot_id,
                violation=ViolationType.LEGAL,
                confidence=vehicle.confidence,
                inside_fraction=best_overlap_frac,
                angle_error_deg=round(d_ang, 1),
            )
        )

    all_legal = all(r.violation == ViolationType.LEGAL for r in results)
    worst = max(results, key=lambda r: (r.violation != ViolationType.LEGAL, r.confidence))

    return ParkingAnalysis(
        vehicle_detected=True,
        slot=results[0].slot_id,
        parking_valid=all_legal,
        violation=None if all_legal else worst.violation,
        confidence=max(d.confidence for d in detections),
        plate=next((d.plate_hint for d in detections if d.plate_hint), None),
        results=results,
    )


def crop_card_image(frame_bgr: np.ndarray, vehicle: Detection) -> np.ndarray | None:
    """Crop upright rectangle around the vehicle card for OCR and review popup."""
    if frame_bgr is None or not vehicle.polygon:
        return None

    pts = np.asarray(vehicle.polygon, dtype=np.float32)
    x, y, w, h = cv2.boundingRect(pts)
    fh, fw = frame_bgr.shape[:2]

    # Add small padding
    pad = 8
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(fw, x + w + pad)
    y2 = min(fh, y + h + pad)

    crop = frame_bgr[y1:y2, x1:x2]
    return crop if crop.size > 0 else None
