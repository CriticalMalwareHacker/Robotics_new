"""Typed API models for parking analysis (Pydantic v2, all inputs validated)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ViolationType(str, Enum):
    LEGAL = "LEGAL"
    OUTSIDE_SLOT = "OUTSIDE_SLOT"
    STRADDLING = "STRADDLING"
    WRONG_ORIENTATION = "WRONG_ORIENTATION"
    NO_PARKING_ZONE = "NO_PARKING_ZONE"


class Detection(BaseModel):
    """One vehicle observation in table coordinates (centimetres)."""

    vehicle_id: str = Field(min_length=1, max_length=64)
    polygon: list[list[float]] = Field(min_length=3, max_length=64)
    angle_deg: float = Field(ge=-360.0, le=360.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    plate_hint: str | None = Field(default=None, max_length=16)
    plate_conf: float | None = Field(default=None, ge=0.0, le=1.0)


class Slot(BaseModel):
    """One parking slot (or restricted zone) in table coordinates (cm)."""

    slot_id: str = Field(min_length=1, max_length=16)
    polygon: list[list[float]] = Field(min_length=3, max_length=64)
    angle_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    restricted: bool = False


class SlotResult(BaseModel):
    vehicle_id: str
    slot_id: str | None = None
    violation: ViolationType = ViolationType.LEGAL
    confidence: float = Field(ge=0.0, le=1.0)
    inside_fraction: float = Field(ge=0.0, le=1.0)
    angle_error_deg: float = Field(ge=0.0, le=90.0)


class ParkingAnalysis(BaseModel):
    vehicle_detected: bool
    slot: str | None = None
    parking_valid: bool = True
    violation: ViolationType | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    plate: str | None = None  # filled by Phase 6 plate reader
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    results: list[SlotResult] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    """Analyze already-detected vehicles (table coordinates, cm).

    The real CV detector (Phase 5) produces these detections; tests and the
    dashboard can POST synthetic ones. No raw images cross the API.
    """

    detections: list[Detection] = Field(default_factory=list, max_length=32)
