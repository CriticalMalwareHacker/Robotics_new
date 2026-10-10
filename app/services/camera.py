"""Hardware USB Camera service with active session management and auto-release."""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
from pathlib import Path
from typing import Generator

import cv2

logger = logging.getLogger(__name__)

class CameraManager:
    """Manages USB camera capture session with auto-shutdown on inactivity."""

    def __init__(self):
        self._lock = threading.Lock()
        self._device_index_lock = threading.Lock()
        self._resolved_device_index: int | None = None
        self._cap: cv2.VideoCapture | None = None
        self._latest_jpeg: bytes | None = None
        self._latest_frame_bgr: any = None
        self._frame_id: int = 0
        self._latest_shape: tuple[int, int] | None = None  # (width, height)
        self._last_brightness: float = 0.0  # mean pixel value; ~0 means black frames
        self._last_access: float = 0
        self._running: bool = False
        self._worker_thread: threading.Thread | None = None

    def _get_device_index(self) -> int:
        forced = os.getenv("CAMERA_INDEX", "").strip()  # multi-cam hosts
        if forced.isdigit():
            return int(forced)
        import platform

        if platform.system() == "Linux":
            for idx in [0, 1, 2]:
                if Path(f"/dev/video{idx}").exists():
                    return idx
            return 0

        # Windows often has a black virtual camera at index 0 and the useful
        # USB camera at index 1. Cache the brightest working candidate so HUD
        # polling does not repeatedly open/close camera devices.
        with self._device_index_lock:
            if self._resolved_device_index is not None:
                return self._resolved_device_index
            best_index = None
            best_brightness = 0.5
            first_open_index = None
            for idx in range(3):
                cap = cv2.VideoCapture(idx)
                try:
                    if not cap.isOpened():
                        continue
                    if first_open_index is None:
                        first_open_index = idx
                    brightness = 0.0
                    for _ in range(8):
                        ok, frame = cap.read()
                        if ok and frame is not None:
                            brightness = max(brightness, float(frame.mean()))
                            if brightness >= 0.5:
                                break
                    if brightness > best_brightness:
                        best_index, best_brightness = idx, brightness
                finally:
                    cap.release()
            # Prefer an image-producing camera, otherwise keep the first
            # openable device so the usual offline/retry behavior still works.
            self._resolved_device_index = (best_index if best_index is not None
                                           else first_open_index if first_open_index is not None
                                           else 0)
            return self._resolved_device_index

    def _open_capture(self, dev_idx: int):
        """Open the native/default camera driver and warm it up.

        CAP_V4L2 is Linux-only. On Windows, use OpenCV's default backend;
        these USB cameras can take several seconds to return a live image.
        If the forced HD mode stays black, reopen at the camera's native size.
        """
        import platform

        if platform.system() == "Linux":
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(dev_idx)
        else:
            cap = cv2.VideoCapture(dev_idx)
        if not cap.isOpened():
            return cap

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        probe = None
        for _ in range(40):
            ok, probe = cap.read()
            if ok and probe is not None and float(probe.mean()) >= 0.5:
                return cap
            time.sleep(0.03)

        logger.warning("Camera %s reads black at 1280x720, falling back to native mode.", dev_idx)
        cap.release()
        cap = cv2.VideoCapture(dev_idx)
        if cap.isOpened():
            for _ in range(40):
                ok, probe = cap.read()
                if ok and probe is not None and float(probe.mean()) >= 0.5:
                    return cap
                time.sleep(0.03)
        return cap

    def _worker(self):
        logger.info("Starting background camera worker (LED turns BLUE)...")
        dev_idx = self._get_device_index()
        cap = self._open_capture(dev_idx)

        if not cap.isOpened():
            logger.error("Could not open USB camera.")
            cap.release()
            self._running = False
            return

        self._cap = cap
        bad = 0

        try:
            while self._running:
                # If no client asked for a frame in >3.0 seconds, auto-release camera to turn LED RED
                if time.time() - self._last_access > 3.0:
                    logger.info("Camera inactive for >3s, shutting down worker (LED turns RED)...")
                    break

                ret, frame = cap.read()
                if not ret or frame is None or float(frame.mean()) < 0.5:
                    bad += 1
                    if bad >= 60:
                        # Dead stream (stuck black): reopen instead of serving black forever.
                        logger.warning("Camera stream dead, reopening device...")
                        try:
                            cap.release()
                        except Exception:
                            pass
                        time.sleep(1.0)
                        cap = self._open_capture(dev_idx)
                        self._cap = cap
                        bad = 0
                        if not cap.isOpened():
                            logger.error("Camera reopen failed.")
                            cap.release()
                            break
                    else:
                        time.sleep(0.03)
                    continue
                bad = 0

                success, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if success:
                    with self._lock:
                        self._latest_jpeg = jpeg.tobytes()
                        self._latest_frame_bgr = frame.copy()
                        self._frame_id += 1
                        self._latest_shape = (int(frame.shape[1]), int(frame.shape[0]))
                        self._last_brightness = float(frame.mean())

                time.sleep(0.03)
        finally:
            cap.release()
            self._cap = None
            self._running = False
            logger.info("Camera released successfully (LED is RED).")

    def ensure_started(self):
        self._last_access = time.time()
        with self._lock:
            if not self._running or self._worker_thread is None or not self._worker_thread.is_alive():
                self._running = True
                self._worker_thread = threading.Thread(target=self._worker, daemon=True)
                self._worker_thread.start()

    def get_frame_meta(self) -> dict:
        """Frame id + size + brightness for HUD overlay sync and diagnostics."""
        self.ensure_started()
        with self._lock:
            w, h = self._latest_shape or (0, 0)
            flowing = self._latest_jpeg is not None
            return {"id": self._frame_id, "width": w, "height": h,
                    "available": flowing,
                    "brightness": round(self._last_brightness, 1)}

    def get_latest_jpeg(self) -> bytes | None:
        self.ensure_started()
        # Camera open and warm-up can take several seconds on Windows USB cams.
        for _ in range(100):
            with self._lock:
                if self._latest_jpeg is not None:
                    return self._latest_jpeg
            time.sleep(0.1)
        return self._latest_jpeg

    def capture_photo(self) -> tuple[bool, str, str]:
        self.ensure_started()
        # Wait for fresh frame
        for _ in range(12):
            with self._lock:
                if self._latest_jpeg is not None:
                    base64_str = f"data:image/jpeg;base64,{base64.b64encode(self._latest_jpeg).decode('utf-8')}"
                    # Mark access time to start countdown to turn off LED
                    self._last_access = time.time() - 2.0  # will release in ~1s
                    return True, base64_str, "Photo captured successfully."
            time.sleep(0.08)
        return False, "", "Could not capture image from USB camera."

    def release_now(self):
        self._running = False
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None


camera_manager = CameraManager()


def get_camera_status() -> dict[str, str | bool | int | float]:
    idx = camera_manager._get_device_index()
    import platform

    exists = platform.system() == "Linux" and Path(f"/dev/video{idx}").exists()
    with camera_manager._lock:
        flowing = camera_manager._latest_jpeg is not None
        brightness = camera_manager._last_brightness
    # A device node alone is not enough; camera readiness requires live frames.
    available = flowing
    if flowing:
        name = f"USB camera (index {idx})"
    elif exists:
        name = f"Camera index {idx} (no frames)"
    else:
        name = f"Camera index {idx} (not detected)"
    return {
        "available": available,
        "name": name,
        "device_index": idx,
        "frames_flowing": flowing,
        "brightness": round(brightness, 1),
    }
