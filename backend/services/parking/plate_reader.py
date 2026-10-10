"""Offline OCR for the tabletop vehicle plate labels.

RapidOCR runs locally using its ONNX Runtime CPU engine. We rectify each
detector polygon from table coordinates back into the camera frame, OCR both
landscape and portrait orientations, and only return a plate when it matches
an Indian registration pattern. Ambiguous text stays blank for manual entry.
"""

from __future__ import annotations

import logging
import re
import threading

import cv2
import numpy as np

from .models import Detection

logger = logging.getLogger(__name__)

_PLATE_PATTERN = re.compile(r"(?:[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{2})")
_engine = None
_engine_lock = threading.Lock()
_engine_error_logged = False


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from rapidocr import RapidOCR
                _engine = RapidOCR()
    return _engine


def _ordered_quad(points: np.ndarray) -> np.ndarray:
    """Return a convex four-point polygon in TL, TR, BR, BL order."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    pts = pts[np.argsort(angles)]
    start = int(np.argmin(pts[:, 0] + pts[:, 1]))
    pts = np.roll(pts, -start, axis=0)
    # In image coordinates this ordering should travel clockwise. Ensure the
    # second point is the upper/right neighbor, not the lower/left neighbor.
    if pts[1, 1] > pts[-1, 1]:
        pts = pts[[0, 3, 2, 1]]
    return pts


def _vehicle_crop(frame: np.ndarray, vehicle: Detection, h_px_to_cm: np.ndarray,
                  calib_size: tuple[int, int]) -> np.ndarray | None:
    fh, fw = frame.shape[:2]
    cw, ch = calib_size
    h_cm_to_px = np.linalg.inv(np.asarray(h_px_to_cm, dtype=np.float64))
    pts_cm = np.asarray(vehicle.polygon, dtype=np.float32).reshape(-1, 1, 2)
    pts_calib = cv2.perspectiveTransform(pts_cm, h_cm_to_px).reshape(4, 2)
    pts = pts_calib * np.asarray([fw / cw, fh / ch], dtype=np.float32)
    src = _ordered_quad(pts)

    top = np.linalg.norm(src[1] - src[0])
    bottom = np.linalg.norm(src[2] - src[3])
    left = np.linalg.norm(src[3] - src[0])
    right = np.linalg.norm(src[2] - src[1])
    width = max(16, int(round(max(top, bottom))))
    height = max(16, int(round(max(left, right))))
    if width < 16 or height < 16:
        return None
    dst = np.asarray([[0, 0], [width - 1, 0],
                      [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(src, dst)
    crop = cv2.warpPerspective(frame, transform, (width, height),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)
    if crop.size == 0:
        return None
    # Keep handwriting and printed labels legible at OCR's detector scale.
    return cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)


def _plate_candidate(result) -> tuple[str | None, float | None]:
    texts = list(getattr(result, "txts", None) or ())
    scores = list(getattr(result, "scores", None) or ())
    boxes = getattr(result, "boxes", None)
    if not texts:
        return None, None

    rows = []
    for i, raw in enumerate(texts):
        text = re.sub(r"[^A-Z0-9]", "", str(raw).upper())
        if not text:
            continue
        score = float(scores[i]) if i < len(scores) else 0.0
        if boxes is not None and i < len(boxes):
            box = np.asarray(boxes[i], dtype=np.float32).reshape(-1, 2)
            x = float(box[:, 0].mean())
            y = float(box[:, 1].mean())
        else:
            x, y = float(i), 0.0
        rows.append((y, x, text, score))
    if not rows:
        return None, None

    # Usually OCR returns a single line. Joining adjacent words also handles
    # labels separated into letter and digit boxes by the text detector.
    rows.sort(key=lambda row: (row[0], row[1]))
    candidates: list[tuple[str, float]] = [(r[2], r[3]) for r in rows]
    joined = "".join(row[2] for row in rows)
    candidates.append((joined, sum(row[3] for row in rows) / len(rows)))

    found: list[tuple[float, str, float]] = []
    for raw, confidence in candidates:
        for match in _PLATE_PATTERN.finditer(raw):
            plate = match.group(0)
            # Prefer a standard plate shape; confidence remains the model's
            # confidence so the HUD can ask the operator to verify it.
            found.append((confidence + 0.05, plate, confidence))
    if not found:
        return None, None
    _, plate, confidence = max(found)
    if confidence < 0.35:
        return None, None
    return plate, round(max(0.0, min(1.0, confidence)), 3)


def read_vehicle_plates(frame: np.ndarray, detections: list[Detection],
                        h_px_to_cm: np.ndarray,
                        calib_size: tuple[int, int]) -> list[Detection]:
    """Return detections with confident plate hints filled where OCR succeeds."""
    global _engine_error_logged
    try:
        engine = _get_engine()
    except Exception as exc:
        if not _engine_error_logged:
            logger.warning("RapidOCR could not initialize; plate OCR disabled: %s", exc)
            _engine_error_logged = True
        return detections

    output = []
    for vehicle in detections:
        try:
            crop = _vehicle_crop(frame, vehicle, h_px_to_cm, calib_size)
            if crop is None:
                output.append(vehicle)
                continue
            crops = (crop, cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE))
            reads = [_plate_candidate(engine(image)) for image in crops]
            best = max((read for read in reads if read[0]),
                       key=lambda read: read[1] or 0.0, default=(None, None))
            if best[0]:
                output.append(vehicle.model_copy(update={
                    "plate_hint": best[0], "plate_conf": best[1]}))
            else:
                output.append(vehicle)
        except Exception as exc:
            logger.debug("OCR failed for %s: %s", vehicle.vehicle_id, exc)
            output.append(vehicle)
    return output
