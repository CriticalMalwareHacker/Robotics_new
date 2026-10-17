"""Combined HUD state: one poll feeds badges, cards, overlay and log.

GET /api/hud/state -> {frame, robot, parking, devices, ticket, events}.
Every field is optional-tolerant: the HUD shows a dash for anything missing
and never crashes. Detections come from the monitor's latest pass (freshness
is reported; the overlay fades when older than 1 s).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.parking import events, monitor
from backend.services.parking.analyzer import load_slots
from backend.services.parking.models import ParkingAnalysis, ViolationType
from backend.services.parking.ticket import LAST, get_history, record_ticket

from .deps import require_api_key
from .robot_routes import _link as _robot_link, _state as _robot_state

router = APIRouter(dependencies=[Depends(require_api_key)])


class ViolationTicketRequest(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=64)
    plate: str = Field(min_length=4, max_length=16)


def _cm_to_px(poly_cm: list[list[float]], h_inv: np.ndarray,
              scale: tuple[float, float] = (1.0, 1.0)) -> list[list[int]]:
    """Table cm -> overlay px. `scale` is (frame/calib) per axis so boxes
    drawn from a 1280x720 calibration land correctly on e.g. 640x480 frames."""
    arr = np.asarray(poly_cm, dtype=np.float32).reshape(-1, 1, 2)
    import cv2
    px = cv2.perspectiveTransform(arr, h_inv).reshape(-1, 2)
    sx, sy = scale
    return [[int(round(float(x) * sx)), int(round(float(y) * sy))] for x, y in px]


def _devices() -> dict:
    try:
        from app.services.camera import camera_manager
        meta_now = camera_manager.get_frame_meta()
        if not meta_now.get("available"):
            cam = "offline"
        elif (meta_now.get("brightness") or 0) < 3:
            cam = "degraded"  # device open but image black: cover, lens, or another app
        else:
            cam = "ok"
    except Exception:
        cam = "offline"
    printer = "offline"
    try:
        printer_transport = os.getenv("PRINTER_TRANSPORT", "usb").lower()
        printer_device = os.getenv("PRINTER_DEVICE", "/dev/usb/lp0")
        if (printer_transport in {"bluetooth", "rfcomm", "serial"}
                and (Path(printer_device).exists() or os.getenv("PRINTER_BLUETOOTH_ADDRESS"))):
            printer = "ok"
        elif Path("/dev/usb/lp0").exists():
            printer = "ok"
        elif os.getenv("HARDWARE_MODE", "pc") == "pc" or os.getenv("MOCK_PRINTER"):
            printer = "simulated"
    except Exception:
        pass
    link = _robot_link()
    return {
        "camera": cam,
        "arduino": link,  # ok | offline | simulated
        "ultrasonic": ("ok" if _robot_state.get("ultrasonic_seen") else
                       ("degraded" if link == "ok" else "offline")),
        "ir": ("ok" if _robot_state.get("ir_seen") else
               ("degraded" if link == "ok" else "offline")),
        "printer": printer,
        "backend": "ok",
    }


@router.get("/api/hud/state")
def hud_state():
    from app.services.camera import camera_manager

    try:
        meta = camera_manager.get_frame_meta()
    except Exception:
        meta = {"id": 0, "width": 0, "height": 0, "available": False}

    m = monitor.status()
    analysis: ParkingAnalysis | None = m["last_analysis"]

    slots = []
    vehicles = []
    try:
        cfg = json.loads((Path(monitor.__file__).parent / "config" / "slots.json")
                         .read_text(encoding="utf-8"))
        h_inv = np.linalg.inv(np.asarray(cfg["homography_px_to_cm"]))
        cw, ch = cfg.get("image_size", [1280, 720])
        fw, fh = meta.get("width") or cw, meta.get("height") or ch
        scale = (fw / cw, fh / ch)
        active_slots = m.get("last_slots") or load_slots()
        for s in active_slots:
            slot_poly_px = s.polygon_px if getattr(s, "polygon_px", None) else _cm_to_px(s.polygon, h_inv, scale)
            slots.append({"name": s.slot_id,
                          "polygon_px": slot_poly_px,
                          "restricted": s.restricted})
        dets = m.get("last_detections", []) if isinstance(m, dict) else []
        by_id = {r.vehicle_id: r for r in (analysis.results if analysis else [])}
        for d in dets:
            r = by_id.get(d.vehicle_id)
            det_poly_px = d.polygon_px if getattr(d, "polygon_px", None) else _cm_to_px(d.polygon, h_inv, scale)
            vehicles.append({
                "id": d.vehicle_id,
                "slot": r.slot_id if r else None,
                "valid": (r.violation == ViolationType.LEGAL) if r else None,
                "violation": r.violation.value if r else None,
                "confidence": d.confidence,
                "polygon_px": det_poly_px,
                "plate": d.plate_hint,
                "plate_conf": d.plate_conf,
            })
    except Exception:
        pass

    robot_state = "ESTOP" if _robot_state["estop"] else {
        "auto": "PATROLLING", "review": "PAUSED_REVIEW", "blocked": "BLOCKED"
    }.get(_robot_state["mode"],
          "MONITORING" if m["monitor"] == "running" else "IDLE")

    return {
        "frame": {"id": meta.get("id", 0), "width": meta.get("width", 0),
                  "height": meta.get("height", 0),
                  "available": meta.get("available", False),
                  "server_time": datetime.now().isoformat(timespec="seconds")},        "robot": {"state": robot_state, "mode": _robot_state["mode"],
                  "link": _robot_link(), "distance_cm": _robot_state.get("distance_cm"),
                  "ir_blocked": _robot_state.get("ir_blocked"),
                  "obstacle": ((_robot_state.get("ir_blocked") is True) or
                               (_robot_state.get("distance_cm") is not None and
                                _robot_state["distance_cm"] <= int(os.getenv("ROBOT_OBSTACLE_CM", "18")))),
                  "review_vehicles": list(_robot_state.get("review_vehicles", [])),
                  "review_confirmed": list(_robot_state.get("review_confirmed", [])),
                  "review_ticketed": list(_robot_state.get("review_ticketed", [])),
                  "review_dismissed": list(_robot_state.get("review_dismissed", [])),
                  "review_ready": (bool(_robot_state.get("review_vehicles")) and
                                   set(_robot_state.get("review_vehicles", [])).issubset(
                                       set(_robot_state.get("review_confirmed", [])) | set(_robot_state.get("review_dismissed", []))) and
                                   set(_robot_state.get("review_vehicles", [])).issubset(
                                       set(_robot_state.get("review_ticketed", [])) | set(_robot_state.get("review_dismissed", [])))),
                  "last_error": _robot_state.get("last_error"),
                  "pose": None, "target": None,
                  "estop": _robot_state["estop"]},
        "parking": {"slots": slots, "vehicles": vehicles,
                    "analyses": m.get("analyses_served", 0),
                    "debounced": m.get("debounced", {})},
        "devices": _devices(),
        "ticket": LAST["ticket"],
        "events": events.latest(),
    }


@router.post("/api/ticket/test-print")
def ticket_test_print():
    """Print a sample violation ticket through the existing printer path."""
    from datetime import datetime

    from app.services.printer import print_label
    from backend.services.parking.ticket import (
        build_ticket_image,
        next_number,
        save_ticket_png,
    )

    number = next_number()
    image = build_ticket_image(number, datetime.now().strftime("%Y-%m-%d %H:%M"),
                               plate="MH01AB1234", vehicle="TEST-001",
                               slot="A3", violation="OUTSIDE_SLOT")
    image_url = save_ticket_png(image, number)
    ok, message = print_label(image)
    record = {"number": number, "status": "printed" if ok else "failed",
              "message": message, "image_url": image_url,
              "plate": "MH01AB1234", "vehicle": "TEST-001", "slot": "A3",
              "violation": "OUTSIDE_SLOT",
              "time": datetime.now().isoformat(timespec="seconds")}
    record_ticket(record)
    events.log("info" if ok else "error",
               "Test ticket printed." if ok
               else "Printer not available. The ticket was saved and can be reprinted.")
    return {"result": "ok" if ok else "saved", **record}


@router.get("/api/ticket/history")
def ticket_history():
    """Return saved parking tickets, newest first."""
    return get_history()


@router.post("/api/ticket/violation")
def ticket_violation(request: ViolationTicketRequest):
    """Print a ticket for a currently visible, currently violating vehicle."""
    plate = re.sub(r"[^A-Z0-9 -]", "", request.plate.strip().upper())
    if len(plate) < 4:
        raise HTTPException(status_code=422, detail="Enter a valid plate (at least 4 letters or digits).")

    if _robot_state.get("mode") == "auto":
        raise HTTPException(status_code=409,
                            detail="Stop or pause the patrol before printing a violation ticket.")
    if _robot_state.get("mode") == "review":
        if request.vehicle_id not in _robot_state.get("review_vehicles", []):
            raise HTTPException(status_code=409,
                                detail="That vehicle is not part of the current patrol review.")
        if request.vehicle_id not in _robot_state.get("review_confirmed", []):
            raise HTTPException(status_code=409,
                                detail="Confirm bad parking before printing this ticket.")

    current = monitor.status()
    analysis: ParkingAnalysis | None = current.get("last_analysis")
    det = next((d for d in current.get("last_detections", [])
                if d.vehicle_id == request.vehicle_id), None)
    result = next((r for r in (analysis.results if analysis else [])
                   if r.vehicle_id == request.vehicle_id), None)
    if det is None or result is None:
        raise HTTPException(status_code=409, detail="That car is no longer visible. Refresh the HUD and try again.")
    if result.violation == ViolationType.LEGAL:
        raise HTTPException(status_code=409, detail="This car is currently parked legally; no ticket was created.")

    from app.services.printer import print_label
    from backend.services.parking.ticket import build_ticket_image, next_number, save_ticket_png

    number = next_number()
    now = datetime.now()
    image = build_ticket_image(number, now.strftime("%Y-%m-%d %H:%M"), plate=plate,
                               vehicle=request.vehicle_id, slot=result.slot_id or "Unknown",
                               violation=result.violation.value)
    image_url = save_ticket_png(image, number)
    ok, message = print_label(image)
    record = {"number": number, "status": "printed" if ok else "failed",
              "message": message, "image_url": image_url, "plate": plate,
              "vehicle": request.vehicle_id, "slot": result.slot_id or "Unknown",
              "violation": result.violation.value, "time": now.isoformat(timespec="seconds")}
    record_ticket(record)
    if ok and _robot_state.get("mode") == "review" and request.vehicle_id in _robot_state.get("review_vehicles", []):
        ticketed = _robot_state.setdefault("review_ticketed", [])
        if request.vehicle_id not in ticketed:
            ticketed.append(request.vehicle_id)
    events.log("info" if ok else "error",
               f"Ticket {number} printed for {plate}." if ok
               else f"Ticket {number} saved, but printer failed: {message}")
    return {"result": "ok" if ok else "saved", **record}
