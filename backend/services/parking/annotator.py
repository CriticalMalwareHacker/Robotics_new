"""Server-side HUD rendering: slots, cars, violations drawn on the frame.

The deployed frontend shows this annotated JPEG directly, so no coordinate
mapping is needed in the browser. Colors (BGR): green legal, red violation,
grey restricted/empty.
"""

from __future__ import annotations

import cv2
import numpy as np

from .models import Detection, ParkingAnalysis, Slot, ViolationType

GREEN = (0, 200, 0)
RED = (0, 0, 255)
GREY = (160, 160, 160)
WHITE = (255, 255, 255)
THICK = 2


def _to_px(poly_cm: list[list[float]], h_inv: np.ndarray,
           scale: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
    """Map table cm -> image px. `scale` rescales calibration-space px to the
    actual frame ((frame_w/calib_w), (frame_h/calib_h)); identity when equal."""
    arr = np.asarray(poly_cm, dtype=np.float32).reshape(-1, 1, 2)
    pts = cv2.perspectiveTransform(arr, h_inv).reshape(-1, 2)
    sx, sy = scale
    if (sx, sy) != (1.0, 1.0):
        pts = pts * np.asarray([sx, sy], dtype=np.float64)
    return pts.astype(int)


def annotate(frame_bgr: np.ndarray, detections: list[Detection],
             analysis: ParkingAnalysis, slots: list[Slot],
             homography: np.ndarray,
             calib_size: tuple[int, int] = (1280, 720)) -> np.ndarray:
    """Draw HUD overlay; returns a new BGR image (input untouched)."""
    img = frame_bgr.copy()
    fh, fw = frame_bgr.shape[:2]
    scale = (fw / calib_size[0], fh / calib_size[1])
    h_inv = np.linalg.inv(np.asarray(homography, dtype=np.float64))
    by_id = {r.vehicle_id: r for r in analysis.results}

    for slot in slots:
        pts = _to_px(slot.polygon, h_inv, scale)
        color = GREY
        if not slot.restricted:
            assigned = [r for r in analysis.results if r.slot_id == slot.slot_id]
            if any(r.violation != ViolationType.LEGAL for r in assigned):
                color = RED
            elif assigned:
                color = GREEN
            else:
                color = WHITE
        cv2.polylines(img, [pts], True, color, THICK)
        x, y = int(pts[:, 0].min()) + 6, int(pts[:, 1].min()) + 24
        cv2.putText(img, slot.slot_id, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, color, 2, cv2.LINE_AA)

    for det in detections:
        px = _to_px(det.polygon, h_inv, scale)
        res = by_id.get(det.vehicle_id)
        color = GREEN if res is None or res.violation == ViolationType.LEGAL else RED
        cv2.polylines(img, [px], True, color, 3)
        x, y = int(px[:, 0].min()), max(20, int(px[:, 1].min()) - 10)
        cv2.putText(img, f"{det.vehicle_id} {res.slot_id or '?'} "
                         f"{res.violation.value if res else ''}",
                    (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

    banner = ("ALL LEGAL" if analysis.parking_valid
              else f"VIOLATION: {analysis.violation.value if analysis.violation else '?'}")
    cv2.putText(img, banner, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                GREEN if analysis.parking_valid else RED, 2, cv2.LINE_AA)
    return img


def encode_jpeg(frame_bgr: np.ndarray, quality: int = 80) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame_bgr,
                           [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return bytes(buf.tobytes())
