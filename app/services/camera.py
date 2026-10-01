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
        self._cap: cv2.VideoCapture | None = None
        self._latest_jpeg: bytes | None = None
        self._latest_frame_bgr: any = None
        self._frame_id: int = 0
        self._latest_shape: tuple[int, int] | None = None  # (width, height)
        self._last_access: float = 0
        self._running: bool = False
        self._worker_thread: threading.Thread | None = None

    def _get_device_index(self) -> int:
        forced = os.getenv("CAMERA_INDEX", "").strip()  # multi-cam hosts
        if forced.isdigit():
            return int(forced)
        for idx in [0, 1, 2]:
            if Path(f"/dev/video{idx}").exists():
                return idx
        return 0

    def _worker(self):
        logger.info("Starting background camera worker (LED turns BLUE)...")
        dev_idx = self._get_device_index()
        cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(dev_idx)

        if not cap.isOpened():
            logger.error("Could not open USB camera.")
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        self._cap = cap

        try:
            while self._running:
                # If no client asked for a frame in >3.0 seconds, auto-release camera to turn LED RED
                if time.time() - self._last_access > 3.0:
                    logger.info("Camera inactive for >3s, shutting down worker (LED turns RED)...")
                    break

                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.03)
                    continue

                success, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if success:
                    with self._lock:
                        self._latest_jpeg = jpeg.tobytes()
                        self._latest_frame_bgr = frame.copy()
                        self._frame_id += 1
                        self._latest_shape = (int(frame.shape[1]), int(frame.shape[0]))

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
        """Frame id + size for HUD overlay sync (additive; jpeg path untouched)."""
        self.ensure_started()
        with self._lock:
            w, h = self._latest_shape or (0, 0)
            return {"id": self._frame_id, "width": w, "height": h,
                    "available": self._latest_jpeg is not None}

    def get_latest_jpeg(self) -> bytes | None:
        self.ensure_started()
        # Wait up to 1.5s for the first frame if just started
        for _ in range(15):
            with self._lock:
                if self._latest_jpeg is not None:
                    return self._latest_jpeg
            time.sleep(0.08)
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


def get_camera_status() -> dict[str, str | bool | int]:
    idx = camera_manager._get_device_index()
    exists = Path(f"/dev/video{idx}").exists()
    return {
        "available": exists,
        "name": "Hikvision 1080P USB Camera" if exists else "None",
        "device_index": idx,
    }
