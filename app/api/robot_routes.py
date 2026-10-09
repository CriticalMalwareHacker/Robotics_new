"""Robot control router with mock mode and optional Uno serial control.

`ROBOT_MODE=mock` (default, no hardware): commands are validated, logged and
acknowledged; link reports "simulated"; distance is unknown (dash in HUD).
`ROBOT_MODE=real`: commands are sent over USB serial to the Uno. The Arduino
sketch must implement the line protocol documented in deploy/ARDUINO_SERIAL.md.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.parking import events, monitor

from .deps import require_api_key
from app.hardware.arduino_serial import arduino_serial

router = APIRouter(dependencies=[Depends(require_api_key)])

_state: dict = {
    "mode": "idle",  # idle | auto
    "estop": False,
    "commands": 0,
    "last_command": None,
}


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


@router.get("/api/robot/status")
def status():
    link = _link()
    return {
        "state": "ESTOP" if _state["estop"] else (
            "PATROLLING" if _state["mode"] == "auto" else "IDLE"),
        "mode": _state["mode"],
        "link": link,
        "serial_port": arduino_serial.port if _real_mode() else None,
        "serial_error": arduino_serial.last_error if _real_mode() and link == "offline" else None,
        "distance_cm": None,  # ultrasonic arrives with the Arduino phase
        "estop": _state["estop"],
        "commands": _state["commands"],
        "last_command": _state["last_command"],
    }


@router.post("/api/robot/command")
def command(cmd: DriveCommand):
    if _state["estop"]:
        raise HTTPException(status_code=409,
                            detail="Emergency stop is active. Clear it first.")
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
    _state["estop"] = True
    _state["mode"] = "idle"
    try:
        monitor.stop()
    except Exception:
        pass
    if _real_mode():
        ok, reply = arduino_serial.request("ESTOP")
        if not ok:
            # Arduino-side movement leases expire on their own; surface the
            # communication failure instead of claiming a confirmed stop.
            raise HTTPException(status_code=503, detail=reply)
    events.log("error", "Emergency stop pressed. Robot halted.")
    return {"status": "estop_active"}


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
    if _state["estop"]:
        raise HTTPException(status_code=409,
                            detail="Emergency stop is active. Clear it first.")
    if _link() == "offline":
        raise HTTPException(status_code=503,
                            detail=arduino_serial.last_error or "No reply from the Arduino. Check the USB cable.")
    if _real_mode():
        raise HTTPException(status_code=501,
                            detail="Autonomous driving is not implemented yet; use Manual drive.")
    _state["mode"] = "auto"
    monitor.start()
    events.log("info", "Auto mode started.")
    return {"status": "auto_started"}


@router.post("/api/robot/auto/stop")
def auto_stop():
    _state["mode"] = "idle"
    monitor.stop()
    if _real_mode() and arduino_serial.connected():
        arduino_serial.request("STOP")
    events.log("info", "Auto mode stopped. Robot is idle.")
    return {"status": "idle"}
