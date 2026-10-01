"""Stage A classical vehicle detector: colored paper cars on a white mat.

No ML. Segments saturated-red + near-black blobs in HSV, cleans with
morphology, and keeps large convex contours (thin slot lines fall out by
area). Contours map to table coordinates (cm) through the calibration
homography. Shadows/glare survive via wide HSV bands + area filtering.
"""

from __future__ import annotations

import cv2
import numpy as np

from .models import Detection

# Tuned on tests/data/mat_baseline.jpg (1280x720, top-down Hikvision).
RED_LO1 = (0, 70, 50)
RED_HI1 = (10, 255, 255)
RED_LO2 = (160, 70, 50)
RED_HI2 = (180, 255, 255)
DARK_HI = (180, 255, 60)  # V <= 60: black car body, not grey shadow
MIN_AREA_PX = 8000
MAX_AREA_PX = 400000
MIN_LONG_SIDE_PX = 60.0


def _long_edge_angle_deg(box: np.ndarray) -> float:
    """Orientation of the longest box edge, folded to [0, 180)."""
    best_len, best_ang = 0.0, 0.0
    for i in range(4):
        d = box[(i + 1) % 4] - box[i]
        ln = float(np.hypot(d[0], d[1]))
        if ln > best_len:
            best_len = ln
            best_ang = float(np.degrees(np.arctan2(d[1], d[0]))) % 180.0
    return best_ang


class ClassicalDetector:
    """Detect paper cars. `homography` maps image px -> table cm.

    `roi_px` is the mat border polygon in px (TL,TR,BR,BL); everything
    outside it (desk, shadows, cables) is ignored before segmentation.
    """

    def __init__(self, homography: np.ndarray,
                 roi_px: list[list[float]] | None = None,
                 min_area_px: int = MIN_AREA_PX,
                 max_area_px: int = MAX_AREA_PX) -> None:
        self.h = np.asarray(homography, dtype=np.float64)
        self.roi_px = roi_px
        self.min_area_px = min_area_px
        self.max_area_px = max_area_px

    def _mask(self, frame_bgr: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        red = (cv2.inRange(hsv, RED_LO1, RED_HI1)
               | cv2.inRange(hsv, RED_LO2, RED_HI2))
        dark = cv2.inRange(hsv, (0, 0, 0), DARK_HI)
        mask = red | dark
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                np.ones((9, 9), np.uint8))
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                np.ones((5, 5), np.uint8))

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        if frame_bgr is None:
            return []
        mask = self._mask(frame_bgr)
        if self.roi_px is not None:  # kill off-mat desk/shadow blobs
            roi = np.zeros(mask.shape, dtype=np.uint8)
            cv2.fillPoly(roi, [np.asarray(self.roi_px, dtype=np.float32)
                               .astype(int)], 255)
            mask = cv2.bitwise_and(mask, roi)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        found: list[tuple[float, np.ndarray, float]] = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if not self.min_area_px <= area <= self.max_area_px:
                continue
            rect = cv2.minAreaRect(cnt)
            (w, h) = rect[1]
            if max(w, h) < MIN_LONG_SIDE_PX:
                continue
            box = cv2.boxPoints(rect).astype(np.float32)  # 4x2 px
            cx = float(box[:, 0].mean())
            ang = _long_edge_angle_deg(box)
            found.append((cx, box, ang))
        found.sort(key=lambda t: t[0])  # left-to-right => stable IDs
        out: list[Detection] = []
        for i, (_, box, ang) in enumerate(found, start=1):
            pts = box.reshape(-1, 1, 2)
            cm = cv2.perspectiveTransform(pts, self.h).reshape(-1, 2)
            out.append(Detection(
                vehicle_id=f"CAR-{i:02d}",
                polygon=[[round(float(x), 2), round(float(y), 2)]
                         for x, y in cm],
                angle_deg=round(ang, 1),
                confidence=0.9,
            ))
        return out


class NullDetector:
    """Fail-safe placeholder: sees nothing. Keeps the API and monitor loop
    runnable when calibration is missing (monitor falls back to this)."""

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:  # noqa: ARG002
        return []
