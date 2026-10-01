"""Single-frame orchestration: detections + slots -> ParkingAnalysis.

The CV detector (Phase 5) produces `Detection`s in table coordinates;
this module classifies each one. Plate text stays None until Phase 6.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import AnalyzeRequest, Detection, ParkingAnalysis, Slot, ViolationType
from .parking_geometry import classify_vehicle

_DEFAULT_SLOTS = Path(__file__).resolve().parent / "config" / "slots.json"


def load_slots(path: str | Path = _DEFAULT_SLOTS) -> list[Slot]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Slot(**s) for s in data.get("slots", [])]


def analyze_frame(detections: list[Detection],
                  slots: list[Slot] | None = None) -> ParkingAnalysis:
    slots = slots if slots is not None else load_slots()
    results = [classify_vehicle(d.polygon, d.angle_deg, slots,
                                confidence=d.confidence,
                                vehicle_id=d.vehicle_id)
               for d in detections]
    if not results:
        return ParkingAnalysis(vehicle_detected=False, parking_valid=True,
                               violation=None, confidence=0.0, results=[])
    first = results[0]
    worst = max(results, key=lambda r: (r.violation != ViolationType.LEGAL,
                                        r.confidence))
    return ParkingAnalysis(
        vehicle_detected=True,
        slot=first.slot_id,
        parking_valid=all(r.violation == ViolationType.LEGAL for r in results),
        violation=None if all(r.violation == ViolationType.LEGAL for r in results)
        else worst.violation,
        confidence=max(d.confidence for d in detections),
        plate=next((d.plate_hint for d in detections if d.plate_hint), None),
        results=results,
    )


def analyze_request(req: AnalyzeRequest,
                    slots: list[Slot] | None = None) -> ParkingAnalysis:
    return analyze_frame(req.detections, slots)
