"""Parking violation detection package (tabletop academic demo)."""

from .analyzer import analyze_frame, load_slots
from .models import (
    AnalyzeRequest,
    Detection,
    ParkingAnalysis,
    Slot,
    SlotResult,
    ViolationType,
)
from .parking_geometry import ViolationDebouncer, classify_vehicle

__all__ = [
    "AnalyzeRequest",
    "Detection",
    "ParkingAnalysis",
    "Slot",
    "SlotResult",
    "ViolationType",
    "ViolationDebouncer",
    "analyze_frame",
    "classify_vehicle",
    "load_slots",
]
