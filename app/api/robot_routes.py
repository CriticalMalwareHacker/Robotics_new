"""Robot control router (additive). Arduino deferred: mock backend.

`ROBOT_MODE=mock` (default, no hardware): commands are validated, logged and
acknowledged; link reports "simulated"; distance is unknown (dash in HUD).
`ROBOT_MODE=real` (Arduino phase): the same endpoints will drive the serial
link; link then reports ok/offline honestly. HUD disables drive controls only
when the link is offline/error, never in mock.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.parking import events, monitor

from .deps import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])

_state: dict = {
    "mode": "idle",  # idle | auto
    "estop": False,
    "commands": 0,
    "last_command": None,
}


def _link() -> str:
    if os.getenv("ROBOT_MODE", "mock").strip().lower() == "real":
        return "offline"  # serial link lands with the Arduino phase
    return "simulated"


class DriveCommand(BaseModel):
    command: Literal["F", "B", "L", "R", "S"]
    speed: int = Field(default=120, ge=0, le=255)
    duration_ms: int = Field(default=200, ge=0, le=5000)


@router.get("/api/robot/status")
def status():
    return {
        "state": "ESTOP" if _state["estop"] else (
            "PATROLLING" if _state["mode"] == "auto" else "IDLE"),
        "mode": _state["mode"],
        "link": _link(),
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
    if _link() == "offline":
        raise HTTPException(status_code=503,
                            detail="No reply from the Arduino. Check the USB cable.")
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
    events.log("error", "Emergency stop pressed. Robot halted.")
    return {"status": "estop_active"}


@router.post("/api/robot/estop/clear")
def estop_clear():
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
                            detail="No reply from the Arduino. Check the USB cable.")
    _state["mode"] = "auto"
    monitor.start()
    events.log("info", "Auto mode started.")
    return {"status": "auto_started"}


@router.post("/api/robot/auto/stop")
def auto_stop():
    _state["mode"] = "idle"
    monitor.stop()
    events.log("info", "Auto mode stopped. Robot is idle.")
    return {"status": "idle"}
