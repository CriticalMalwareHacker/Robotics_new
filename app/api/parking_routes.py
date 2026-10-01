"""Parking analysis router (additive; existing routers untouched).

Detections arrive in table coordinates (cm) — the CV detector (Phase 5)
produces them from the overhead frame; tests and the HUD can POST synthetic
ones. Auth: `require_api_key` (open when API_KEY env is empty).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.services.parking.analyzer import analyze_request, load_slots
from backend.services.parking.models import AnalyzeRequest, ParkingAnalysis

from .deps import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])

_LAST: dict = {"analysis": None, "count": 0}


@router.post("/api/parking/analyze", response_model=ParkingAnalysis)
def analyze(req: AnalyzeRequest):
    """Classify posted detections against slots.json; store as latest."""
    analysis = analyze_request(req)
    _LAST["analysis"] = analysis
    _LAST["count"] += 1
    return analysis


@router.get("/api/parking/status")
def status():
    """Latest analysis + monitor state (monitor loop lands with detector)."""
    return {
        "monitor": "stopped",
        "detector": "null",
        "slots_loaded": len(load_slots()),
        "analyses_served": _LAST["count"],
        "last_analysis": _LAST["analysis"],
    }
