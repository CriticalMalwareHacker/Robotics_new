"""Parking robot router (additive; existing routers untouched).

- POST /api/parking/analyze: classify posted detections (table coords, cm).
- GET  /api/parking/status: monitor state + latest analysis (HUD polls this).
- POST /api/parking/monitor/start|stop: 1 Hz detect->analyze->debounce loop.
- GET  /api/parking/frame: live annotated JPEG for the HUD <img>.
Auth: `require_api_key` (open when API_KEY env is empty).
"""

from __future__ import annotations

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.services.parking import monitor
from backend.services.parking.analyzer import analyze_frame, analyze_request, load_slots
from backend.services.parking.annotator import annotate, encode_jpeg
from backend.services.parking.models import AnalyzeRequest, ParkingAnalysis

from .deps import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])

_LAST: dict = {"analysis": None, "count": 0}

_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.post("/api/parking/analyze", response_model=ParkingAnalysis)
def analyze(req: AnalyzeRequest):
    """Classify posted detections against slots.json; store as latest."""
    analysis = analyze_request(req)
    _LAST["analysis"] = analysis
    _LAST["count"] += 1
    return analysis


@router.get("/api/parking/status")
def status():
    """Monitor state + latest analysis (direct posts win if monitor idle)."""
    m = monitor.status()
    last = m["last_analysis"] or _LAST["analysis"]
    return {
        **m,
        "slots_loaded": len(load_slots()),
        "direct_analyses": _LAST["count"],
        "last_analysis": last,
    }


@router.post("/api/parking/monitor/start")
def monitor_start():
    return monitor.start()


@router.post("/api/parking/monitor/stop")
def monitor_stop():
    return monitor.stop()


@router.get("/api/parking/frame")
def frame():
    """Live annotated JPEG: slots, cars, violations drawn server-side."""
    from app.services.camera import camera_manager

    jpeg = camera_manager.get_latest_jpeg()
    if jpeg is None:
        raise HTTPException(status_code=503, detail="Camera frame not ready.")
    frame_bgr = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8),
                             cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise HTTPException(status_code=503, detail="Camera frame undecodable.")

    detector, slots = monitor.load_detector()
    detections = detector.detect(frame_bgr)
    analysis = analyze_frame(detections, slots)

    import json
    from pathlib import Path
    cfg = json.loads((Path(monitor.__file__).parent / "config" / "slots.json")
                     .read_text(encoding="utf-8"))
    annotated = annotate(frame_bgr, detections, analysis, slots,
                         np.asarray(cfg["homography_px_to_cm"]))
    return Response(content=encode_jpeg(annotated), media_type="image/jpeg",
                    headers=dict(_NO_CACHE))


@router.get("/api/parking/stream")
def stream():
    """MJPEG multipart stream for the HUD <img>. Falls back to /frame polling."""
    from fastapi.responses import StreamingResponse

    from app.services.camera import camera_manager

    def gen():
        import time
        while True:
            jpeg = camera_manager.get_latest_jpeg()
            if jpeg is not None:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(jpeg)).encode() +
                       b"\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(0.1)

    return StreamingResponse(gen(),
                             media_type="multipart/x-mixed-replace; boundary=frame")
