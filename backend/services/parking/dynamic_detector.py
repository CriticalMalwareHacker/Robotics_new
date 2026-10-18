"""Dynamic Computer Vision Pipeline for ParkSensei.

Detects:
1. Dynamic parking bays formed by black marker lines drawn on a floor / mat.
2. Rectangular colored cards (yellow, red, black, etc.) and box cars placed as vehicles.
3. Tight perspective-accurate vehicle boundaries (quadrilaterals).
4. Evaluates parking violations dynamically relative to detected lines:
   - STRADDLING: Vehicle overlaps or crosses a parking divider line into an adjacent bay.
   - WRONG_ORIENTATION: Vehicle angle deviates from parking bay lines by > 25 deg.
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

# Orientation tolerance (accommodates perspective foreshortening in wide-angle views)
MAX_ANGLE_ERROR_DEG = 25.0


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
    parking area, and paper_mask is the raw threshold mask for bright white paper.
    """
    fh, fw = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    # Detect white/light paper surface (neutral white has very low saturation S <= 65)
    paper_mask = cv2.inRange(hsv, (0, 0, 110), (180, 65, 255))
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


def _order_quad_clockwise(pts: np.ndarray | Sequence[Sequence[float]]) -> np.ndarray:
    """Order 4 polygon vertices in clockwise sequence around their centroid."""
    arr = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
    if len(arr) < 3:
        return arr
    cx, cy = float(np.mean(arr[:, 0])), float(np.mean(arr[:, 1]))
    angles = np.arctan2(arr[:, 1] - cy, arr[:, 0] - cx)
    sort_idx = np.argsort(angles)
    return arr[sort_idx]


def extract_tight_card_polygon(cnt: np.ndarray) -> np.ndarray:
    """Extract a perspective-accurate tight 4-corner polygon for a vehicle card.
    
    Handles perspective foreshortening (where cards on a table appear as trapezoids
    rather than orthogonal rectangles), avoiding the oversized box artifacts of minAreaRect.
    """
    hull = cv2.convexHull(cnt)
    hull_pts = hull.reshape(-1, 2)
    if len(hull_pts) <= 4:
        return _order_quad_clockwise(hull_pts)

    peri = cv2.arcLength(hull, True)
    hull_area = cv2.contourArea(hull)

    # 1. Multi-scale polygon approximation to find exact 4 convex corners
    for eps_factor in [0.03, 0.04, 0.05, 0.06, 0.02, 0.07]:
        approx = cv2.approxPolyDP(hull, eps_factor * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            approx_area = cv2.contourArea(approx)
            if approx_area >= 0.85 * hull_area:
                return _order_quad_clockwise(approx.reshape(4, 2))

    # 2. Fit 4 extreme vertices of the hull closest to the minAreaRect bounding corners
    rect = cv2.minAreaRect(hull)
    box = cv2.boxPoints(rect)
    corners: list[np.ndarray] = []
    used_indices: set[int] = set()

    for b_pt in box:
        dists = [math.hypot(hp[0] - b_pt[0], hp[1] - b_pt[1]) for hp in hull_pts]
        sorted_indices = np.argsort(dists)
        for idx in sorted_indices:
            if idx not in used_indices:
                used_indices.add(int(idx))
                corners.append(hull_pts[idx])
                break

    if len(corners) == 4:
        return _order_quad_clockwise(corners)
    return _order_quad_clockwise(box)


def detect_vehicle_cards(frame_bgr: np.ndarray) -> list[Detection]:
    """Detect colored rectangular cards (yellow, red, black, etc.) on the parking surface."""
    if frame_bgr is None or frame_bgr.size == 0:
        return []

    fh, fw = frame_bgr.shape[:2]
    mat_mask, paper_mask = _extract_mat_mask(frame_bgr)

    min_card_area = fh * fw * 0.008
    max_card_area = fh * fw * 0.35

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    non_white = cv2.bitwise_and(cv2.bitwise_not(paper_mask), mat_mask)

    # Dedicated color channel segmentation prevents adjacent colored cards from merging
    # Red channel (Hue wraps around 0 and 180)
    red_mask = (cv2.inRange(hsv, (0, 50, 50), (15, 255, 255)) | cv2.inRange(hsv, (160, 50, 50), (180, 255, 255))) & mat_mask
    # Yellow channel (Hue 16..45)
    yellow_mask = cv2.inRange(hsv, (16, 45, 60), (45, 255, 255)) & mat_mask
    # Other saturated color channel (Blue, Green, etc. Hue 46..159)
    other_sat_mask = cv2.inRange(hsv, (46, 50, 50), (159, 255, 255)) & mat_mask
    # Dark/Neutral/Black channel on the mat
    dark_neutral_mask = non_white & cv2.bitwise_not(red_mask | yellow_mask | other_sat_mask)

    open_k = max(5, int(min(fh, fw) * 0.02) | 1)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (open_k, open_k))

    raw_candidates: list[tuple[float, float, np.ndarray, float]] = []
    channels = [red_mask, yellow_mask, other_sat_mask, dark_neutral_mask]

    for mask_ch in channels:
        opened = cv2.morphologyEx(mask_ch, cv2.MORPH_OPEN, k)
        cnts, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = float(cv2.contourArea(c))
            if not (min_card_area <= area <= max_card_area):
                continue

            c_hull = cv2.convexHull(c)
            hull_area = float(cv2.contourArea(c_hull))
            if not (min_card_area <= hull_area <= max_card_area):
                continue

            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < 0.60:
                continue

            rect = cv2.minAreaRect(c_hull)
            (cx, cy), (rw, rh), _ = rect
            if min(rw, rh) < 12:
                continue

            aspect = max(rw, rh) / min(rw, rh)
            if not (1.05 <= aspect <= 4.5):
                continue

            # Strict Mat Enclosure: Discard candidate if >= 20% of its area lies outside the white mat
            cand_mask = np.zeros((fh, fw), dtype=np.uint8)
            cv2.drawContours(cand_mask, [c_hull], -1, 255, -1)
            inside_mat = cv2.countNonZero(cv2.bitwise_and(cand_mask, mat_mask))
            total_cand = cv2.countNonZero(cand_mask)
            if total_cand > 0 and (inside_mat / total_cand) < 0.80:
                continue

            # Extract tight 4-corner perspective quad
            poly = extract_tight_card_polygon(c)
            if len(poly) < 4:
                continue

            # Determine vehicle driving orientation (angle of side edges closer to vertical/perspective)
            dx_side = (poly[2][0] - poly[1][0] + poly[3][0] - poly[0][0]) / 2.0
            dy_side = (poly[2][1] - poly[1][1] + poly[3][1] - poly[0][1]) / 2.0
            side_ang = float(math.degrees(math.atan2(dy_side, dx_side))) % 180.0

            dx_top = (poly[1][0] - poly[0][0] + poly[2][0] - poly[3][0]) / 2.0
            dy_top = (poly[1][0] - poly[0][0] + poly[2][1] - poly[3][1]) / 2.0
            top_ang = float(math.degrees(math.atan2(dy_top, dx_top))) % 180.0

            best_ang = side_ang if abs(side_ang - 90.0) <= abs(top_ang - 90.0) else top_ang
            raw_candidates.append((cx, cy, poly, best_ang))

    # Deduplicate overlapping detections across color channels
    filtered: list[tuple[float, float, np.ndarray, float]] = []
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
    for i, (cx, cy, poly, ang) in enumerate(filtered, start=1):
        poly_list = [[round(float(p[0]), 1), round(float(p[1]), 1)] for p in poly]
        poly_px = [[int(round(p[0])), int(round(p[1]))] for p in poly]

        detections.append(
            Detection(
                vehicle_id=f"CAR-{i:02d}",
                polygon=poly_list,
                angle_deg=round(ang, 1),
                confidence=0.94,
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
    dil_k = max(7, int(min(fh, fw) * 0.02) | 1)
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

    # Determine vertical span of the parking area
    y_indices = np.where(mat_mask > 0)[0]
    y_top = float(y_indices.min() + 5) if len(y_indices) > 0 else float(fh * 0.3)
    y_bot = float(y_indices.max() - 5) if len(y_indices) > 0 else float(fh * 0.95)

    def _x_at_y(l_seg: tuple[int, int, int, int, float], target_y: float) -> float:
        lx1, ly1, lx2, ly2, _ = l_seg
        if abs(ly2 - ly1) < 1e-4:
            return float(lx1)
        return float(lx1) + (target_y - ly1) * (lx2 - lx1) / (ly2 - ly1)

    ref_y = float(fh * 0.85)
    cluster_dist_thresh = max(22.0, fw * 0.055)

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

    # Cluster length filter: Real marker divider lines have substantial length across the mat
    # Stray specks, noise, or short shadows (< 22% of mat height) are rejected
    min_cluster_len = max(30.0, (y_bot - y_top) * 0.22)
    valid_clusters = [
        cl for cl in clusters
        if sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in cl) >= min_cluster_len
    ]

    merged_lines: list[tuple[float, float, float, float, float]] = []
    for cl in valid_clusters:
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

    # Deduplicate lines that are too close to each other
    dedupe_dist = max(38.0, fw * 0.085)
    deduped_lines: list[tuple[float, float, float, float, float]] = []
    for l in merged_lines:
        if not deduped_lines:
            deduped_lines.append(l)
        else:
            prev = deduped_lines[-1]
            l_avg = (l[0] + l[2]) / 2
            prev_avg = (prev[0] + prev[2]) / 2
            if abs(l_avg - prev_avg) < dedupe_dist:
                continue
            deduped_lines.append(l)

    # Form dynamic parking bays between adjacent pairs of divider lines
    bays: list[Slot] = []
    min_slot_width = max(25.0, fw * 0.06)
    max_slot_width = fw * 0.65

    for idx in range(len(deduped_lines) - 1):
        l1 = deduped_lines[idx]
        l2 = deduped_lines[idx + 1]

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

    line_segments = [
        (int(round(l[0])), int(round(l[1])), int(round(l[2])), int(round(l[3])))
        for l in deduped_lines
    ]
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
