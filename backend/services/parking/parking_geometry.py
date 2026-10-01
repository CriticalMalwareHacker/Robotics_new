"""Pure parking geometry + violation rules.

No I/O, no ML, no hardware. All functions are deterministic and unit-tested
with synthetic polygons in table coordinates (centimetres). Slots and cars
are treated as convex polygons (mat slots and rotated car boxes always are).

Thresholds (from build brief, tuned on synthetic cases in tests/):
- INSIDE_FRACTION: car needs >= 80% of its area inside one slot.
- STRADDLE_FRACTION: overlap >= 15% with each of two slots => straddling.
- RESTRICTED_FRACTION: overlap >= 10% with a restricted zone => violation.
- MAX_ANGLE_ERROR_DEG: heading vs slot axis tolerance is 25 degrees.
"""

from __future__ import annotations

from collections import deque
from typing import Sequence

import cv2
import numpy as np

from .models import Slot, SlotResult, ViolationType

INSIDE_FRACTION = 0.80
STRADDLE_FRACTION = 0.15
RESTRICTED_FRACTION = 0.10
MAX_ANGLE_ERROR_DEG = 25.0


def _contour(poly: Sequence[Sequence[float]]) -> np.ndarray:
    return np.asarray(poly, dtype=np.float32).reshape(-1, 1, 2)


def polygon_area(poly: Sequence[Sequence[float]]) -> float:
    """Absolute area of a polygon (0.0 for degenerate input)."""
    arr = np.asarray(poly, dtype=np.float32)
    if arr.shape[0] < 3:
        return 0.0
    return float(abs(cv2.contourArea(_contour(poly))))


def overlap_fraction(car_poly: Sequence[Sequence[float]],
                     slot_poly: Sequence[Sequence[float]]) -> float:
    """Fraction of the *car* area lying inside the slot, in [0, 1]."""
    car_area = polygon_area(car_poly)
    if car_area <= 0:
        return 0.0
    try:
        _ret, inter = cv2.intersectConvexConvex(
            np.asarray(car_poly, dtype=np.float32),
            np.asarray(slot_poly, dtype=np.float32),
        )
    except cv2.error:
        return 0.0
    if inter is None or len(inter) == 0:
        return 0.0
    inter_area = float(abs(cv2.contourArea(inter)))
    return max(0.0, min(1.0, inter_area / car_area))


def angle_diff_deg(a: float, b: float) -> float:
    """Smallest heading difference folded to [0, 90].

    Parking slots are axes (0 deg == 180 deg), so the error folds at 90.
    """
    d = abs(float(a) - float(b)) % 180.0
    if d > 90.0:
        d = 180.0 - d
    return d


def build_homography(src_pts: Sequence[Sequence[float]],
                     dst_pts: Sequence[Sequence[float]]) -> np.ndarray:
    """Perspective map for 4 mat-corner markers: image px -> table cm."""
    src = np.asarray(src_pts, dtype=np.float32)
    dst = np.asarray(dst_pts, dtype=np.float32)
    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError("homography needs exactly 4 source and 4 destination points")
    return cv2.getPerspectiveTransform(src, dst)


def apply_homography(h: np.ndarray,
                     pts: Sequence[Sequence[float]]) -> list[list[float]]:
    """Map points through a 3x3 homography; returns [[x, y], ...]."""
    arr = np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2)
    mapped = cv2.perspectiveTransform(arr, np.asarray(h, dtype=np.float64))
    return [[float(x), float(y)] for x, y in mapped.reshape(-1, 2)]


def classify_vehicle(car_poly: Sequence[Sequence[float]], car_angle_deg: float,
                     slots: Sequence[Slot], confidence: float = 1.0,
                     vehicle_id: str = "") -> SlotResult:
    """Apply violation rules in priority order; first match wins.

    Priority: NO_PARKING_ZONE > STRADDLING > OUTSIDE_SLOT > WRONG_ORIENTATION
    > LEGAL. `slot_id` is None when the car meaningfully overlaps nothing.
    """
    overlaps = [(s, overlap_fraction(car_poly, s.polygon)) for s in slots]

    for slot, frac in overlaps:
        if slot.restricted and frac >= RESTRICTED_FRACTION:
            return SlotResult(vehicle_id=vehicle_id, slot_id=slot.slot_id,
                              violation=ViolationType.NO_PARKING_ZONE,
                              confidence=confidence, inside_fraction=frac,
                              angle_error_deg=angle_diff_deg(car_angle_deg, slot.angle_deg))

    open_hits = [(s, f) for s, f in overlaps if not s.restricted and f >= STRADDLE_FRACTION]
    if len(open_hits) >= 2:
        open_hits.sort(key=lambda t: t[1], reverse=True)
        top, frac = open_hits[0]
        return SlotResult(vehicle_id=vehicle_id, slot_id=top.slot_id,
                          violation=ViolationType.STRADDLING,
                          confidence=confidence, inside_fraction=frac,
                          angle_error_deg=angle_diff_deg(car_angle_deg, top.angle_deg))

    open_all = [(s, f) for s, f in overlaps if not s.restricted]
    best_slot, best_frac = (max(open_all, key=lambda t: t[1])
                            if open_all else (None, 0.0))
    if best_slot is None or best_frac < INSIDE_FRACTION:
        slot_id = (best_slot.slot_id if best_slot is not None
                   and best_frac >= STRADDLE_FRACTION else None)
        return SlotResult(vehicle_id=vehicle_id, slot_id=slot_id,
                          violation=ViolationType.OUTSIDE_SLOT,
                          confidence=confidence, inside_fraction=best_frac,
                          angle_error_deg=0.0)

    err = angle_diff_deg(car_angle_deg, best_slot.angle_deg)
    if err > MAX_ANGLE_ERROR_DEG:
        return SlotResult(vehicle_id=vehicle_id, slot_id=best_slot.slot_id,
                          violation=ViolationType.WRONG_ORIENTATION,
                          confidence=confidence, inside_fraction=best_frac,
                          angle_error_deg=err)

    return SlotResult(vehicle_id=vehicle_id, slot_id=best_slot.slot_id,
                      violation=ViolationType.LEGAL,
                      confidence=confidence, inside_fraction=best_frac,
                      angle_error_deg=err)


class ViolationDebouncer:
    """A violation counts only if seen in >= `need` of the last `window` frames."""

    def __init__(self, window: int = 8, need: int = 5) -> None:
        if not 1 <= need <= window:
            raise ValueError("need must satisfy 1 <= need <= window")
        self.window = window
        self.need = need
        self._hist: dict[str, deque[bool]] = {}

    def update(self, key: str, violated: bool) -> bool:
        hist = self._hist.setdefault(key, deque(maxlen=self.window))
        hist.append(bool(violated))
        return sum(hist) >= self.need

    def reset(self, key: str) -> None:
        self._hist.pop(key, None)
