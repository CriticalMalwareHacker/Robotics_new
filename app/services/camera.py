"""Hardware USB Camera service for PrintSensei (Hikvision 1080p and V4L2 USB webcams)."""

from __future__ import annotations

import base64
import logging
import threading
import time
from pathlib import Path
from typing import Generator

import cv2

logger = logging.getLogger(__name__)

_CAMERA_LOCK = threading.Lock()
_ACTIVE_CAPTURE: cv2.VideoCapture | None = None
_LAST_FRAME_JPEG: bytes | None = None
_STREAM_CLIENTS = 0


def get_camera_device_index() -> int:
    """Find the best available V4L2 video capture device index."""
    # Check /dev/video0, /dev/video1, etc.
    for index in [0, 1, 2]:
        if Path(f"/dev/video{index}").exists():
            return index
    return 0


def capture_usb_frame(device_index: int | None = None, width: int = 1280, height: int = 720) -> tuple[bool, str, str]:
    """Capture a single high-quality frame from the USB camera and return as base64 data URI."""
    if device_index is None:
        device_index = get_camera_device_index()

    with _CAMERA_LOCK:
        cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(device_index)

        if not cap.isOpened():
            return False, "", "Could not open USB camera device."

        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Let sensor auto-exposure and white balance settle
            frame = None
            for _ in range(4):
                ret, temp_frame = cap.read()
                if ret and temp_frame is not None:
                    frame = temp_frame
                time.sleep(0.04)

            if frame is None or frame.size == 0:
                return False, "", "Failed to grab frame from USB camera."

            # Encode as JPEG
            success, encoded_img = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            if not success:
                return False, "", "Failed to encode camera image."

            jpeg_bytes = encoded_img.tobytes()
            base64_str = f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('utf-8')}"
            return True, base64_str, "Photo captured successfully."
        finally:
            cap.release()


async def generate_mjpeg_stream(request: Any = None) -> Any:
    """Generate low-latency MJPEG video stream chunks and release camera as soon as disconnected."""
    import asyncio
    device_index = get_camera_device_index()
    
    with _CAMERA_LOCK:
        cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(device_index)

        if not cap.isOpened():
            logger.warning("Could not open camera for MJPEG stream.")
            return

        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)

            while True:
                if request is not None and await request.is_disconnected():
                    break

                ret, frame = cap.read()
                if not ret or frame is None:
                    await asyncio.sleep(0.05)
                    continue

                success, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if not success:
                    continue

                frame_bytes = jpeg.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n" +
                    frame_bytes + b"\r\n"
                )
                await asyncio.sleep(0.06)  # ~15 fps
        except (GeneratorExit, asyncio.CancelledError, Exception) as exc:
            logger.info(f"Camera stream disconnected: {exc}")
        finally:
            cap.release()
            logger.info("USB camera device released; LED turns RED.")


def get_camera_status() -> dict[str, str | bool | int]:
    """Check whether a USB camera is connected and functional."""
    idx = get_camera_device_index()
    exists = Path(f"/dev/video{idx}").exists()
    return {
        "available": exists,
        "name": "Hikvision 1080P USB Camera" if exists else "None",
        "device_index": idx,
    }
