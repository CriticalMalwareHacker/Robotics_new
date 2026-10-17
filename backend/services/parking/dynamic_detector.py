"""Dynamic Computer Vision Pipeline for ParkSensei.

Detects:
1. Dynamic parking bays formed by black marker lines drawn on a floor / mat.
2. Rectangular colored cards and box cars placed as vehicles.
3. Evaluates parking violations dynamically relative to detected lines:
   - STRADDLING: Vehicle overlaps or crosses a parking divider line into an adjacent bay.
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


def _extract_mat_mask(frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Isolate the white/bright parking surface mat (paper sheet or floor ROI).
    
    Returns (mat_mask, paper_mask) where mat_mask is the filled convex region of the
    parking area, and paper_mask is the raw threshold mask for bright paper.
    """
    fh, fw = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    # Detect white/light paper surface
    paper_mask = cv2.inRange(hsv, (0, 0, 110), (180, 85, 255))
    cnts, _ = cv2.findContours(paper_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mat_mask = np.zeros((fh, fw), dtype=np.uint8)
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        # If paper sheet covers at least 8% of the frame
        if cv2.contourArea(largest) >= (fh * fw * 0.08):
            hull = cv2.convexHull(largest)
            cv2.drawContours(mat_mask, [hull], -1, 255, -1)

    # Fallback to lower 70% if no distinct paper sheet is detected (e.g. uniform floor)
    if cv2.countNonZero(mat_mask) == 0:
        roi_top = int(fh * 0.28)
        mat_mask[roi_top:fh, 0:fw] = 255
        paper_mask[roi_top:fh, 0:fw] = 255

    return mat_mask, paper_mask


def detect_vehicle_cards(frame_bgr: np.ndarray) -> list[Detection]:
    """Detect colored rectangular cards or box cars on the parking surface."""
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    fh, fw = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mat_mask, paper_mask = _extract_mat_mask(frame_bgr)

    min_card_area = fh * fw * 0.008
    max_card_area = fh * fw * 0.35

    # 1. Non-white regions on the mat that survive opening (removes thin 2-6px marker lines)
    non_white = cv2.bitwise_and(cv2.bitwise_not(paper_mask), mat_mask)
    open_k = max(7, int(min(fh, fw) * 0.025) | 1)
    close_k = max(7, int(min(fh, fw) * 0.03) | 1)
    cards_opened = cv2.morphologyEx(non_white, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k)))

    # 2. Saturated colored cards (red, blue, green, yellow, orange)
    # Red wrap-around hue
    red_mask = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 45, 40), (15, 255, 255)),
        cv2.inRange(hsv, (160, 45, 40), (180, 255, 255))
    )
    # High-saturation other colors
    sat_mask = cv2.inRange(hsv, (16, 45, 40), (159, 255, 255))
    color_mask = cv2.bitwise_and(cv2.bitwise_or(red_mask, sat_mask), mat_mask)
    color_opened = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k)))
    color_closed = cv2.morphologyEx(color_opened, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (close_k, close_k)))

    # Combined candidate mask inside the mat
    candidate_mask = cv2.bitwise_or(cards_opened, color_closed)
    candidate_mask = cv2.bitwise_and(candidate_mask, mat_mask)

    cnts, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    raw_candidates: list[tuple[float, float, tuple, np.ndarray, float]] = []
    for c in cnts:
        area = float(cv2.contourArea(c))
        if not (min_card_area <= area <= max_card_area):
            continue

        c_hull = cv2.convexHull(c)
        hull_area = float(cv2.contourArea(c_hull))
        if not (min_card_area <= hull_area <= max_card_area):
            continue

        rect = cv2.minAreaRect(c_hull)
        (cx, cy), (rw, rh), _ = rect
        if min(rw, rh) < 12:
            continue

        aspect = max(rw, rh) / min(rw, rh)
        if not (1.05 <= aspect <= 4.5):
            continue

        box = cv2.boxPoints(rect)

        # Calculate vehicle driving orientation in [0, 180)
        # Choose the axis closest to vertical / perspective (typically 45-135 deg)
        ang1 = float(math.degrees(math.atan2(box[1][1] - box[0][1], box[1][0] - box[0][0]))) % 180.0
        ang2 = float(math.degrees(math.atan2(box[2][1] - box[1][1], box[2][0] - box[1][0]))) % 180.0
        
        diff1 = abs(ang1 - 90.0)
        diff2 = abs(ang2 - 90.0)
        best_ang = ang1 if diff1 <= diff2 else ang2

        raw_candidates.append((cx, cy, rect, box, best_ang))

    # Deduplicate overlapping detections (e.g. if color and dark contour both caught same card)
    filtered: list[tuple[float, float, tuple, np.ndarray, float]] = []
    for cand in raw_candidates:
        cx1, cy1 = cand[0], cand[1]
        dup = False
        for existing in filtered:
            cx2, cy2 = existing[0], existing[1]
            if math.hypot(cx1 - cx2, cy1 - cy2) < (min(fh, fw) * 0.08):
                dup = True
                break
        if not dup:
            filtered.append(cand)

    # Sort left-to-right by center x for consistent vehicle IDs
    filtered.sort(key=lambda c: c[0])

    detections: list[Detection] = []
    for i, (cx, cy, rect, box, ang) in enumerate(filtered, start=1):
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


def detect_marker_lines_and_bays(frame_bgr: np.ndarray) -> tuple[list[Slot], list[tuple[int, int, int, int]]]:
    """Detect black marker lines on the parking surface and group them into dynamic bays."""
    if frame_bgr is None or frame_bgr.size == 0:
        return [], []

    fh, fw = frame_bgr.shape[:2]
    mat_mask, _ = _extract_mat_mask(frame_bgr)

    # Detect cards first so their footprints are excluded from marker line detection
    cards = detect_vehicle_cards(frame_bgr)
    cards_mask = np.zeros((fh, fw), dtype=np.uint8)
    for c in cards:
        pts = np.asarray(c.polygon_px, dtype=np.int32)
        cv2.fillPoly(cards_mask, [pts], 255)

    # Dilate card masks slightly so card edges don't get detected as lines
    dil_k = max(5, int(min(fh, fw) * 0.015) | 1)
    cards_dilated = cv2.dilate(cards_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (dil_k, dil_k)))
    mat_inner = cv2.erode(mat_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6)))

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold to isolate dark marker strokes
    block_size = max(15, int(min(fh, fw) * 0.05) | 1)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=block_size, C=10
    )

    # Restrict strictly to inner mat area, excluding cards
    lines_only = cv2.bitwise_and(thresh, mat_inner)
    lines_only = cv2.bitwise_and(lines_only, cv2.bitwise_not(cards_dilated))

    min_len = max(12, int(min(fh, fw) * 0.04))
    max_gap = max(10, int(min(fh, fw) * 0.03))

    lines_p = cv2.HoughLinesP(
        lines_only, rho=1, theta=np.pi / 180,
        threshold=14, minLineLength=min_len, maxLineGap=max_gap
    )

    if lines_p is None:
        return [], []

    # Filter vertical / perspective divider line segments
    vert_lines: list[tuple[int, int, int, int, float]] = []
    for line in lines_p:
        vals = np.asarray(line).reshape(-1)
        if len(vals) < 4:
            continue
        x1, y1, x2, y2 = int(vals[0]), int(vals[1]), int(vals[2]), int(vals[3])
        ang = _line_angle_deg(x1, y1, x2, y2)

        # Keep divider lines angled between 25.0 and 155.0 deg
        if 25.0 <= ang <= 155.0:
            if y1 > y2:
                x1, y1, x2, y2 = x2, y2, x1, y1
            vert_lines.append((x1, y1, x2, y2, ang))

    if not vert_lines:
        return [], []

    # Project lines to baseline to cluster collinear/perspective dividers
    def _x_at_y(l_seg: tuple[int, int, int, int, float], target_y: float) -> float:
        lx1, ly1, lx2, ly2, _ = l_seg
        if abs(ly2 - ly1) < 1e-4:
            return float(lx1)
        return float(lx1) + (target_y - ly1) * (lx2 - lx1) / (ly2 - ly1)

    ref_y = float(fh * 0.85)
    cluster_dist_thresh = max(25.0, fw * 0.06)

    clusters: list[list[tuple[int, int, int, int, float]]] = []
    for l_seg in vert_lines:
        x_ref = _x_at_y(l_seg, ref_y)
        matched = False
        for cl in clusters:
            cl_avg_x = float(np.mean([_x_at_y(m, ref_y) for m in cl]))
            if abs(x_ref - cl_avg_x) < cluster_dist_thresh:
                cl.append(l_seg)
                matched = True
                break
        if not matched:
            clusters.append([l_seg])

    # Determine vertical span of the parking area
    y_indices = np.where(mat_mask > 0)[0]
    y_top = float(y_indices.min() + 5) if len(y_indices) > 0 else float(fh * 0.3)
    y_bot = float(y_indices.max() - 5) if len(y_indices) > 0 else float(fh * 0.95)

    merged_lines: list[tuple[float, float, float, float, float]] = []
    for cl in clusters:
        pts = []
        for l_seg in cl:
            pts.extend([(l_seg[0], l_seg[1]), (l_seg[2], l_seg[3])])
        pts_arr = np.array(pts, dtype=np.float32)
        vx, vy, x0, y0 = cv2.fitLine(pts_arr, cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy, x0, y0 = float(vx[0]), float(vy[0]), float(x0[0]), float(y0[0])

        if abs(vy) > 1e-4:
            xt = x0 + (y_top - y0) * (vx / vy)
            xb = x0 + (y_bot - y0) * (vx / vy)
            ang = _line_angle_deg(xt, y_top, xb, y_bot)
            merged_lines.append((xt, y_top, xb, y_bot, ang))

    # Sort lines left-to-right by average x
    merged_lines.sort(key=lambda l: (l[0] + l[2]) / 2)

    # Form dynamic parking bays between adjacent pairs of divider lines
    bays: list[Slot] = []
    min_slot_width = max(20.0, fw * 0.05)
    max_slot_width = fw * 0.60

    for idx in range(len(merged_lines) - 1):
        l1 = merged_lines[idx]
        l2 = merged_lines[idx + 1]

        w_top = abs(l2[0] - l1[0])
        w_bot = abs(l2[2] - l1[2])
        w_avg = (w_top + w_bot) / 2

        if min_slot_width <= w_avg <= max_slot_width:
            bay_poly = [
                [round(l1[0], 1), round(l1[1], 1)],
                [round(l2[0], 1), round(l2[1], 1)],
                [round(l2[2], 1), round(l2[3], 1)],
                [round(l1[2], 1), round(l1[3], 1)],
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

    line_segments = [(int(round(l[0])), int(round(l[1])), int(round(l[2])), int(round(l[3]))) for l in merged_lines]
    return bays, line_segments


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

        # Calculate overlap fraction with each bay
        bay_overlaps: list[tuple[Slot, float]] = []
        for bay in bays:
            bay_poly = np.asarray(bay.polygon, dtype=np.float32)
            try:
                _ret, inter = cv2.intersectConvexConvex(car_poly, bay_poly)
                if inter is not None and len(inter) > 0:
                    inter_area = float(abs(cv2.contourArea(inter)))
                    frac = min(1.0, inter_area / car_area)
                    if frac >= 0.05:
                        bay_overlaps.append((bay, frac))
            except cv2.error:
                continue

        bay_overlaps.sort(key=lambda b: b[1], reverse=True)
        best_bay = bay_overlaps[0][0] if bay_overlaps else None
        best_overlap_frac = bay_overlaps[0][1] if bay_overlaps else 0.0

        # Check straddling:
        # 1. Multi-bay straddling: vehicle overlaps 2+ bays with second bay >= 12%
        is_straddling = (len(bay_overlaps) >= 2 and bay_overlaps[1][1] >= 0.12)

        # 2. Divider line intersection: divider line passes through vehicle interior
        if not is_straddling and len(lines) >= 2:
            car_min_y = min(p[1] for p in vehicle.polygon)
            car_max_y = max(p[1] for p in vehicle.polygon)

            # Check internal divider lines (exclude outermost borders)
            internal_lines = lines[1:-1] if len(lines) > 2 else lines
            for lx1, ly1, lx2, ly2 in internal_lines:
                # Vertical overlap check
                l_min_y = min(ly1, ly2)
                l_max_y = max(ly1, ly2)
                if car_max_y < l_min_y or car_min_y > l_max_y:
                    continue

                dx = float(lx2 - lx1)
                dy = float(ly2 - ly1)
                signs = []
                for pt in vehicle.polygon:
                    cross = dx * (pt[1] - ly1) - dy * (pt[0] - lx1)
                    signs.append(1 if cross > 25.0 else (-1 if cross < -25.0 else 0))

                has_pos = any(s == 1 for s in signs)
                has_neg = any(s == -1 for s in signs)
                if has_pos and has_neg:
                    is_straddling = True
                    break

        if is_straddling:
            results.append(
                SlotResult(
                    vehicle_id=vehicle.vehicle_id,
                    slot_id=best_bay.slot_id if best_bay else None,
                    violation=ViolationType.STRADDLING,
                    confidence=vehicle.confidence,
                    inside_fraction=best_overlap_frac,
                    angle_error_deg=0.0,
                )
            )
            continue

        # If not inside any bay (overlap < 65%)
        if best_bay is None or best_overlap_frac < 0.65:
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

        # Check vehicle driving orientation alignment with the parking bay
        # Check both bounding box axes (long and short) against the bay angle
        pts = vehicle.polygon
        ax1_ang = _line_angle_deg(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        ax2_ang = _line_angle_deg(pts[1][0], pts[1][1], pts[2][0], pts[2][1])

        d1 = abs(ax1_ang - best_bay.angle_deg) % 180.0
        if d1 > 90.0:
            d1 = 180.0 - d1
        d2 = abs(ax2_ang - best_bay.angle_deg) % 180.0
        if d2 > 90.0:
            d2 = 180.0 - d2

        d_ang = min(d1, d2)

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

        # Clean and aligned inside bay
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
