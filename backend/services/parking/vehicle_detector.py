"""Vehicle detector interface (Stage A classical detector lands in Phase 5).

Detectors output `Detection`s in **table coordinates (cm)** — the homography
from mat-corner markers is applied inside the detector, so `analyzer` and
geometry never see pixels.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from .models import Detection


class VehicleDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        """Return vehicle detections for one BGR frame (table coords, cm)."""
        ...


class NullDetector:
    """Placeholder: sees nothing. Keeps the API and monitor loop runnable
    (fail-safe) until the classical detector is implemented."""

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:  # noqa: ARG002
        return []
