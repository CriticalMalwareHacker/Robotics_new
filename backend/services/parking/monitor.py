"""1 Hz monitor loop: frame -> detect -> analyze -> debounce -> remember.

Runs in a daemon thread; any hardware failure degrades to last-known state
(never crashes the app). Frame provider is injectable for tests.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import cv2
import numpy as np

from .analyzer import analyze_frame, load_slots
from .models import ParkingAnalysis, Slot
from .parking_geometry import ViolationDebouncer
from .vehicle_detector import ClassicalDetector, NullDetector

logger = logging.getLogger(__name__)

_state: dict = {
    "running": False,
    "thread": None,
    "last_analysis": None,
    "debounced": {},
    "analyses": 0,
}
_lock = threading.RLock()  # reentrant: start()/stop() report status() while holding it


def _default_provider() -> np.ndarray | None:
    try:
        from app.services.camera import camera_manager
        jpeg = camera_manager.get_latest_jpeg()
    except Exception as exc:  # fail-safe: no camera, no crash
        logger.warning("monitor: camera unavailable: %s", exc)
        return None
    if jpeg is None:
        return None
    return cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)


def load_detector():
    """Build the classical detector from slots.json calibration (public for reuse)."""
    try:
        slots: list[Slot] = load_slots()
        import json
        from pathlib import Path
        cfg = json.loads((Path(__file__).parent / "config" / "slots.json")
                         .read_text(encoding="utf-8"))
        cfg = json.loads((Path(__file__).parent / "config" / "slots.json")
                         .read_text(encoding="utf-8"))
        h = np.asarray(cfg["homography_px_to_cm"], dtype=np.float64)
        roi = cfg.get("corners_px_TL_TR_BR_BL")
        return ClassicalDetector(h, roi_px=roi), slots
    except Exception as exc:
        logger.warning("monitor: calibration missing, detector null: %s", exc)
        return NullDetector(), []


def _loop(provider: Callable[[], np.ndarray | None], interval_s: float) -> None:
    detector, slots = load_detector()
    deb = ViolationDebouncer()
    while _state["running"]:
        try:
            frame = provider()
            dets = detector.detect(frame) if frame is not None else []
            analysis = analyze_frame(dets, slots)
            flags = {r.vehicle_id: deb.update(r.vehicle_id,
                                              r.violation.value != "LEGAL")
                     for r in analysis.results}
            with _lock:
                _state["last_analysis"] = analysis
                _state["debounced"] = flags
                _state["analyses"] += 1
        except Exception as exc:  # never kill the app on a bad frame
            logger.warning("monitor tick failed: %s", exc)
        time.sleep(interval_s)


def start(provider: Callable[[], np.ndarray | None] | None = None,
          interval_s: float = 1.0) -> dict:
    """Start monitoring (idempotent). Returns current monitor state."""
    with _lock:
        if _state["running"]:
            return status()
        _state["running"] = True
        _state["thread"] = threading.Thread(
            target=_loop, args=(provider or _default_provider, interval_s),
            daemon=True)
        _state["thread"].start()
        return status()


def stop() -> dict:
    with _lock:
        _state["running"] = False
        th = _state["thread"]
        _state["thread"] = None
    if th is not None:
        th.join(timeout=3.0)
    return status()


def status() -> dict:
    with _lock:
        last: ParkingAnalysis | None = _state["last_analysis"]
        return {
            "monitor": "running" if _state["running"] else "stopped",
            "analyses_served": _state["analyses"],
            "debounced": dict(_state["debounced"]),
            "last_analysis": last,
        }
