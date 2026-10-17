"""Robot control router with mock mode and optional Uno serial control.

`ROBOT_MODE=mock` (default, no hardware): commands are validated, logged and
acknowledged; link reports "simulated"; distance is unknown (dash in HUD).
`ROBOT_MODE=real`: commands are sent over USB serial to the Uno. The Arduino
sketch must implement the line protocol documented in deploy/ARDUINO_SERIAL.md.
"""

from __future__ import annotations

import concurrent.futures
import logging
import math
import os
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.parking import events, monitor

from .deps import require_api_key
from app.hardware.arduino_serial import arduino_serial

logger = logging.getLogger(__name__)
_sensor_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sensor_reader")

router = APIRouter(dependencies=[Depends(require_api_key)])

_state: dict = {
    "mode": "idle",  # idle | auto | review | blocked
    "estop": False,
    "commands": 0,
    "last_command": None,
    "distance_cm": None,
    "ir_blocked": None,
    "sensor_seen": False,
    "ultrasonic_seen": False,
    "ir_seen": False,
    "review_vehicles": [],
    "review_confirmed": [],
    "review_ticketed": [],
    "review_dismissed": [],
}
_auto_stop_event = threading.Event()
_auto_thread: threading.Thread | None = None
_auto_command_lock = threading.Lock()
_suppressed_violations: set[str] = set()
_ir_sensor = None
_ir_sensor_lock = threading.Lock()
_ultrasonic_sensor = None
_ultrasonic_sensor_lock = threading.Lock()


def _serial(command: str) -> tuple[bool, str]:
    ok, reply = arduino_serial.request(command)
    if not ok:
        _state["last_error"] = reply
    return ok, reply


def _auto_serial(command: str, *, stopping: bool = False) -> tuple[bool, str]:
    """Serialize patrol commands with Stop/E-stop and reject late drive leases."""
    with _auto_command_lock:
        if _auto_stop_event.is_set() and not stopping:
            return False, "Auto stop requested."
        return _serial(command)


def _read_ir_blocked() -> bool:
    """Read the HW-201's active-low OUT signal on the Pi (BCM GPIO22)."""
    global _ir_sensor
    try:
        with _ir_sensor_lock:
            if _ir_sensor is None:
                from gpiozero import DigitalInputDevice

                gpio = int(os.getenv("ROBOT_IR_GPIO", "22"))
                _ir_sensor = DigitalInputDevice(gpio, pull_up=False)
            # HW-201 OUT goes low when it detects a reflective obstacle.
            return bool(_ir_sensor.value == 0)
    except Exception as exc:
        logger.debug("IR sensor read failed: %s", exc)
        return False


def _read_ultrasonic_raw() -> float:
    """Internal reader: instantiate DistanceSensor with partial=True and small max_distance."""
    global _ultrasonic_sensor
    with _ultrasonic_sensor_lock:
        if _ultrasonic_sensor is None:
            from gpiozero import DistanceSensor

            trigger = int(os.getenv("ROBOT_ULTRASONIC_TRIGGER_GPIO", "5"))
            echo = int(os.getenv("ROBOT_ULTRASONIC_ECHO_GPIO", "6"))
            # partial=True avoids blocking on full queue; max_distance=1.5 limits pulse timeout
            _ultrasonic_sensor = DistanceSensor(
                echo=echo, trigger=trigger, max_distance=1.5, queue_len=2, partial=True
            )
        dist = _ultrasonic_sensor.distance
        if dist is None or math.isnan(dist):
            return 0.0
        return float(dist) * 100.0


def _read_ultrasonic_cm() -> float:
    """Read the HC-SR04 through a Pi-safe ECHO divider with a hard 0.25s timeout."""
    try:
        future = _sensor_executor.submit(_read_ultrasonic_raw)
        return future.result(timeout=0.25)
    except concurrent.futures.TimeoutError:
        logger.debug("Ultrasonic sensor read timed out (no echo pulse).")
        return 0.0
    except Exception as exc:
        logger.debug("Ultrasonic sensor read failed: %s", exc)
        return 0.0


def _sensor_reading() -> tuple[bool, bool]:
    # Both sensors are on the Pi now. Arduino serial remains the motor-control link.
    distance_cm = _read_ultrasonic_cm()
    ir_blocked = _read_ir_blocked()
    distance = int(round(distance_cm)) if distance_cm > 0 else 0
    _state["distance_cm"] = distance if distance > 0 else None
    _state["ir_blocked"] = ir_blocked
    _state["sensor_seen"] = True
    _state["ultrasonic_seen"] = (distance_cm > 0)
    _state["ir_seen"] = True
    obstacle = ir_blocked or (distance > 0 and distance <= int(os.getenv("ROBOT_OBSTACLE_CM", "18")))
    return obstacle, ir_blocked


def _auto_loop(baseline_analyses: int) -> None:
    """Short-lease forward patrol; stop on sensor obstruction or a new violation."""
    speed = max(1, min(255, int(os.getenv("ROBOT_AUTO_PWM", "255"))))
    lease_ms = max(100, min(500, int(os.getenv("ROBOT_AUTO_LEASE_MS", "220"))))
    turn_ms = max(100, min(500, int(os.getenv("ROBOT_AUTO_TURN_MS", "350"))))
    turn = "L"
    blocked_turns = 0
    last_analysis_count = baseline_analyses
    last_vision_progress = time.monotonic()
    try:
        vision_startup_timeout = max(5.0, float(os.getenv("ROBOT_VISION_STARTUP_TIMEOUT_S", "20")))
    except ValueError:
        vision_startup_timeout = 20.0
    vision_ready = False
    obstacle_samples = 0

    while not _auto_stop_event.is_set() and _state["mode"] == "auto":
        try:
            from app.services.camera import camera_manager
            if not camera_manager.get_frame_meta().get("available"):
                raise RuntimeError("Camera feed unavailable during patrol.")
        except Exception as exc:
            _auto_serial("STOP", stopping=True)
            _state["mode"] = "blocked"
            _state["last_error"] = f"Camera check failed; patrol stopped: {exc}"
            events.log("error", _state["last_error"])
            return

        # Pause the car for operator review only after the monitor has produced
        # fresh frames since Start auto.
        vision = monitor.status()
        analysis_count = vision.get("analyses_served", 0)
        if analysis_count > last_analysis_count:
            last_analysis_count = analysis_count
            last_vision_progress = time.monotonic()
            vision_ready = True
        elif time.monotonic() - last_vision_progress > (5.0 if vision_ready else vision_startup_timeout):
            _auto_serial("STOP", stopping=True)
            _state["mode"] = "blocked"
            _state["last_error"] = "Parking camera analysis stopped updating; patrol stopped."
            events.log("error", _state["last_error"])
            return

        if vision_ready:
            flags = vision.get("debounced", {})
            _suppressed_violations.intersection_update(
                vid for vid, active in flags.items() if active)
            violations = sorted(vid for vid, active in flags.items()
                                if active and vid not in _suppressed_violations)
            if violations:
                stopped, stop_reply = _auto_serial("STOP", stopping=True)
                if not stopped:
                    _state["mode"] = "blocked"
                    _state["last_error"] = f"Could not confirm stop for parking review: {stop_reply}"
                    events.log("error", _state["last_error"])
                    return
                _state["mode"] = "review"
                _state["review_vehicles"] = violations
                _state["review_confirmed"] = []
                _state["review_ticketed"] = []
                _state["review_dismissed"] = []
                _state["last_error"] = None
                events.log("warn", "Patrol paused for parking review: " + ", ".join(violations))
                return

        if not vision_ready:
            _auto_stop_event.wait(0.08)
            continue

        try:
            obstacle, _ = _sensor_reading()
        except Exception as exc:
            _auto_serial("STOP", stopping=True)
            _state["mode"] = "blocked"
            _state["last_error"] = f"Sensor/serial read failed; patrol stopped: {exc}"
            events.log("error", _state["last_error"])
            return

        if obstacle:
            obstacle_samples += 1
            stopped, stop_reply = _auto_serial("STOP", stopping=True)
            if not stopped:
                _state["mode"] = "blocked"
                _state["last_error"] = f"Could not confirm stop at obstacle: {stop_reply}"
                events.log("error", _state["last_error"])
                return
            # Require a 2nd confirmation reading before taking avoidance action
            if obstacle_samples < 2:
                _auto_stop_event.wait(0.08)
                continue
            obstacle_samples = 0
            blocked_turns += 1
            if blocked_turns > 4:
                _state["mode"] = "blocked"
                _state["last_error"] = "Obstacle still detected after multiple escape attempts; patrol stopped."
                events.log("warn", _state["last_error"])
                return

            # 1. Reverse for clearance to keep front corners from scraping/binding
            events.log("info", "Obstacle confirmed. Backing up for clearance...")
            _auto_serial(f"MOVE B {speed} 250")
            _auto_stop_event.wait(0.28)
            _auto_serial("STOP", stopping=True)
            _auto_stop_event.wait(0.05)

            # 2. Consistent escape turn: don't immediately ping-pong back into obstacle
            current_turn = turn if blocked_turns <= 2 else ("R" if turn == "L" else "L")
            turn_duration = turn_ms if blocked_turns < 3 else min(500, int(turn_ms * 1.4))
            events.log("info", f"Obstacle avoidance pivot {current_turn} ({turn_duration}ms)...")
            turned, turn_reply = _auto_serial(f"MOVE {current_turn} {speed} {turn_duration}")
            if not turned:
                if _auto_stop_event.is_set():
                    break
                _state["mode"] = "blocked"
                _state["last_error"] = f"Obstacle-avoidance turn failed: {turn_reply}"
                events.log("error", _state["last_error"])
                return
            _auto_stop_event.wait(turn_duration / 1000.0 + 0.06)
            stopped, stop_reply = _auto_serial("STOP", stopping=True)
            if not stopped:
                _state["mode"] = "blocked"
                _state["last_error"] = f"Could not confirm stop after turn: {stop_reply}"
                events.log("error", _state["last_error"])
                return
            _auto_stop_event.wait(0.05)
            continue

        obstacle_samples = 0
        blocked_turns = 0
        ok, reply = _auto_serial(f"MOVE F {speed} {lease_ms}")
        if not ok:
            if _auto_stop_event.is_set():
                break
            _state["mode"] = "blocked"
            _state["last_error"] = f"Patrol command failed; stopped: {reply}"
            events.log("error", _state["last_error"])
            return
        _auto_stop_event.wait(0.06)

    _auto_serial("STOP", stopping=True)


def _real_mode() -> bool:
    return os.getenv("ROBOT_MODE", "mock").strip().lower() == "real"


def _link() -> str:
    if not _real_mode():
        return "simulated"
    return "ok" if arduino_serial.connected() else "offline"


class DriveCommand(BaseModel):
    command: Literal["F", "B", "L", "R", "S"]
    speed: int = Field(default=120, ge=0, le=255)
    duration_ms: int = Field(default=200, ge=0, le=5000)


class ReviewConfirmation(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=64)


@router.get("/api/robot/status")
def status():
    link = _link()
    return {
        "state": "ESTOP" if _state["estop"] else {
            "auto": "PATROLLING", "review": "PAUSED_REVIEW", "blocked": "BLOCKED"
        }.get(_state["mode"], "IDLE"),
        "mode": _state["mode"],
        "link": link,
        "serial_port": arduino_serial.port if _real_mode() else None,
        "serial_error": arduino_serial.last_error if _real_mode() and link == "offline" else None,
        "distance_cm": _state["distance_cm"],
        "ir_blocked": _state["ir_blocked"],
        "obstacle": ((_state["ir_blocked"] is True) or
                     (_state["distance_cm"] is not None and
                      _state["distance_cm"] <= int(os.getenv("ROBOT_OBSTACLE_CM", "18")))),
        "review_vehicles": list(_state["review_vehicles"]),
        "review_confirmed": list(_state["review_confirmed"]),
        "review_ticketed": list(_state["review_ticketed"]),
        "review_dismissed": list(_state.get("review_dismissed", [])),
        "review_ready": (bool(_state["review_vehicles"]) and
                         set(_state["review_vehicles"]).issubset(
                             set(_state["review_confirmed"]) | set(_state.get("review_dismissed", []))
                         ) and
                         set(_state["review_vehicles"]).issubset(
                             set(_state["review_ticketed"]) | set(_state.get("review_dismissed", []))
                         )),
        "last_error": _state.get("last_error"),
        "estop": _state["estop"],
        "commands": _state["commands"],
        "last_command": _state["last_command"],
    }


@router.post("/api/robot/command")
def command(cmd: DriveCommand):
    if _state["estop"]:
        raise HTTPException(status_code=409,
                            detail="Emergency stop is active. Clear it first.")
    if _state["mode"] in {"auto", "review"}:
        raise HTTPException(status_code=409,
                            detail="Stop autonomous patrol before using manual drive.")
    link = _link()
    if link == "offline":
        raise HTTPException(status_code=503,
                            detail=arduino_serial.last_error or "No reply from the Arduino. Check the USB cable.")
    if _real_mode():
        wire_command = "STOP" if cmd.command == "S" else (
            f"MOVE {cmd.command} {cmd.speed} {cmd.duration_ms}")
        ok, reply = arduino_serial.request(wire_command)
        if not ok:
            raise HTTPException(status_code=503, detail=reply)
    _state["commands"] += 1
    _state["last_command"] = cmd.model_dump()
    events.log("info", f"Drive {cmd.command} at {cmd.speed} PWM.")
    return {"status": "ok", "link": _link(), **cmd.model_dump()}


@router.post("/api/robot/estop")
def estop():
    _auto_stop_event.set()
    _state["estop"] = True
    _state["mode"] = "idle"
    # Keep vision running for HUD feedback; E-stop halts motion, not sensing.
    if _real_mode():
        with _auto_command_lock:
            ok, reply = arduino_serial.request("ESTOP")
        if not ok:
            # Arduino-side movement leases expire on their own; surface the
            # communication failure instead of claiming a confirmed stop.
            raise HTTPException(status_code=503, detail=reply)
    events.log("error", "Emergency stop pressed. Robot halted.")
    return {"status": "estop_active"}


@router.post("/api/robot/review/confirm")
def review_confirm(request: ReviewConfirmation):
    """Record the operator's explicit bad-parking confirmation for a review car."""
    if _state["mode"] != "review":
        raise HTTPException(status_code=409, detail="There is no parking review in progress.")
    if request.vehicle_id not in _state["review_vehicles"]:
        raise HTTPException(status_code=404, detail="That vehicle is not part of this review.")
    if request.vehicle_id not in _state["review_confirmed"]:
        _state["review_confirmed"].append(request.vehicle_id)
    return {"status": "confirmed", "vehicle_id": request.vehicle_id}


@router.post("/api/robot/review/dismiss")
def review_dismiss(request: ReviewConfirmation):
    """Dismiss a review car (e.g. false detection or manual override) to unblock patrol."""
    if _state["mode"] != "review":
        raise HTTPException(status_code=409, detail="There is no parking review in progress.")
    if request.vehicle_id not in _state["review_vehicles"]:
        raise HTTPException(status_code=404, detail="That vehicle is not part of this review.")
    if request.vehicle_id not in _state.setdefault("review_dismissed", []):
        _state["review_dismissed"].append(request.vehicle_id)
    events.log("info", f"Vehicle {request.vehicle_id} dismissed by operator.")
    return {"status": "dismissed", "vehicle_id": request.vehicle_id}


@router.post("/api/robot/estop/clear")
def estop_clear():
    if _real_mode():
        ok, reply = arduino_serial.request("CLEAR")
        if not ok:
            raise HTTPException(status_code=503, detail=reply)
    _state["estop"] = False
    events.log("info", "Emergency stop cleared. Robot ready.")
    return {"status": "ready"}


@router.post("/api/robot/auto/start")
def auto_start():
    if _state["mode"] in {"auto", "review"}:
        raise HTTPException(status_code=409,
                            detail="Autonomous patrol is already running.")
    if _state["estop"]:
        raise HTTPException(status_code=409,
                            detail="Emergency stop is active. Clear it first.")
    if _link() == "offline":
        raise HTTPException(status_code=503,
                            detail=arduino_serial.last_error or "No reply from the Arduino. Check the USB cable.")
    if _real_mode():
        try:
            from app.services.camera import camera_manager
            if not camera_manager.get_frame_meta().get("available"):
                raise HTTPException(status_code=503,
                                    detail="Camera is unavailable; patrol needs its live parking view.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503,
                                detail=f"Camera preflight failed: {exc}") from exc
        try:
            _sensor_reading()
        except Exception as exc:
            logger.warning("Obstacle sensor preflight note: %s", exc)
            events.log("warn", f"Sensor preflight warning: {exc}")
        ok, reply = _serial("STOP")
        if not ok:
            raise HTTPException(status_code=503,
                                detail=f"Could not confirm an idle robot before patrol: {reply}")
    global _auto_thread
    _auto_stop_event.set()
    if _auto_thread and _auto_thread.is_alive():
        _auto_thread.join(timeout=0.5)
    _suppressed_violations.clear()
    _state["mode"] = "auto"
    _state["review_vehicles"] = []
    _state["review_confirmed"] = []
    _state["review_ticketed"] = []
    _state["review_dismissed"] = []
    _state["last_error"] = None
    monitor.start()
    if _real_mode():
        baseline = monitor.status().get("analyses_served", 0)
        _auto_stop_event.clear()
        _auto_thread = threading.Thread(target=_auto_loop, args=(baseline,), daemon=True)
        _auto_thread.start()
    events.log("info", "Auto mode started.")
    return {"status": "auto_started"}


@router.post("/api/robot/auto/stop")
def auto_stop():
    _auto_stop_event.set()
    if _real_mode():
        with _auto_command_lock:
            ok, reply = _serial("STOP")
        if not ok:
            raise HTTPException(status_code=503, detail=reply)
    _state["mode"] = "idle"
    _state["review_vehicles"] = []
    _state["review_confirmed"] = []
    _state["review_ticketed"] = []
    _state["review_dismissed"] = []
    # Monitoring is independent from driving and stays available in idle mode.
    events.log("info", "Auto mode stopped. Robot is idle.")
    return {"status": "idle"}


@router.post("/api/robot/auto/resume")
def auto_resume():
    global _auto_thread
    if _state["estop"]:
        raise HTTPException(status_code=409,
                            detail="Emergency stop is active. Clear it first.")
    if _state["mode"] != "review":
        raise HTTPException(status_code=409,
                            detail="Patrol is not paused for review.")
    confirmed_or_dismissed = set(_state["review_confirmed"]) | set(_state.get("review_dismissed", []))
    ticketed_or_dismissed = set(_state["review_ticketed"]) | set(_state.get("review_dismissed", []))
    if not (set(_state["review_vehicles"]).issubset(confirmed_or_dismissed) and
            set(_state["review_vehicles"]).issubset(ticketed_or_dismissed)):
        raise HTTPException(status_code=409,
                            detail="Confirm & ticket or dismiss each review vehicle before continuing.")
    if _link() == "offline":
        raise HTTPException(status_code=503,
                            detail=arduino_serial.last_error or "No reply from the Arduino.")
    _suppressed_violations.update(_state["review_vehicles"])
    _state["review_vehicles"] = []
    _state["review_confirmed"] = []
    _state["review_ticketed"] = []
    _state["review_dismissed"] = []
    _state["mode"] = "auto"
    _state["last_error"] = None
    if _real_mode():
        if _auto_thread and _auto_thread.is_alive():
            _auto_stop_event.set()
            _auto_thread.join(timeout=0.5)
        _auto_stop_event.clear()
        baseline = monitor.status().get("analyses_served", 0)
        _auto_thread = threading.Thread(target=_auto_loop, args=(baseline,), daemon=True)
        _auto_thread.start()
    events.log("info", "Parking reviewed; auto patrol resumed.")
    return {"status": "auto_resumed"}
