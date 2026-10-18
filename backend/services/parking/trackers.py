"""Temporal smoothing and tracking for dynamic parking bays and vehicle detections.

Prevents HUD and auto-mode decision flickering caused by chassis vibration,
momentary lighting fluctuations, or camera frame dropouts.
"""

from __future__ import annotations

import math
from typing import Sequence

from .models import Detection, Slot


def _polygon_centroid(poly: Sequence[Sequence[float]]) -> tuple[float, float]:
    """Calculate the (cx, cy) arithmetic centroid of a polygon."""
    if not poly:
        return 0.0, 0.0
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return cx, cy


class BayGridTracker:
    """Maintains temporal stability of detected parking bays.
    
    If chassis movement momentarily obscures a divider line, the previously
    confirmed stable bay grid is retained for a short grace window (e.g., 3 frames).
    """

    def __init__(self, max_hold_frames: int = 3) -> None:
        self.max_hold_frames = max_hold_frames
        self.stable_bays: list[Slot] = []
        self.stable_lines: list[tuple[int, int, int, int]] = []
        self.hold_frames_remaining: int = 0

    def update(
        self,
        bays: list[Slot],
        lines: list[tuple[int, int, int, int]],
    ) -> tuple[list[Slot], list[tuple[int, int, int, int]]]:
        # High confidence grid detection: 2 or more bays formed by clear divider lines
        if len(bays) >= 2:
            self.stable_bays = list(bays)
            self.stable_lines = list(lines)
            self.hold_frames_remaining = self.max_hold_frames
            return bays, lines

        # Transient dropout: single-frame blur or vibration dropped lines
        if self.stable_bays and self.hold_frames_remaining > 0:
            self.hold_frames_remaining -= 1
            return list(self.stable_bays), list(self.stable_lines)

        # Clear expired cache if no bays seen after hold period
        if bays:
            return bays, lines
        return [], []

    def reset(self) -> None:
        self.stable_bays = []
        self.stable_lines = []
        self.hold_frames_remaining = 0


class TrackedVehicle:
    def __init__(self, detection: Detection) -> None:
        self.detection = detection
        self.cx, self.cy = _polygon_centroid(detection.polygon)
        self.miss_count: int = 0
        self.hit_count: int = 1

    def update(self, new_det: Detection) -> None:
        # Preserve OCR plate reading across frames if new frame momentarily blurs OCR
        plate_hint = new_det.plate_hint or self.detection.plate_hint
        plate_conf = new_det.plate_conf if new_det.plate_hint else self.detection.plate_conf

        self.detection = Detection(
            vehicle_id=self.detection.vehicle_id,
            polygon=new_det.polygon,
            angle_deg=new_det.angle_deg,
            confidence=max(self.detection.confidence, new_det.confidence),
            plate_hint=plate_hint,
            plate_conf=plate_conf,
            polygon_px=new_det.polygon_px,
        )
        self.cx, self.cy = _polygon_centroid(new_det.polygon)
        self.miss_count = 0
        self.hit_count += 1


class VehicleTracker:
    """Tracks vehicle card observations across consecutive video frames.
    
    Associates vehicles by centroid proximity, preserves recognized license plates
    against transient OCR dropouts, and prevents flickering from 1-frame misses.
    """

    def __init__(self, max_miss_frames: int = 1, match_dist_px: float = 65.0) -> None:
        self.max_miss_frames = max_miss_frames
        self.match_dist_px = match_dist_px
        self.tracks: list[TrackedVehicle] = []
        self.next_vehicle_idx: int = 1

    def update(self, detections: list[Detection]) -> list[Detection]:
        if not detections and not self.tracks:
            return []

        # Calculate centroids of incoming detections
        unmatched_dets = list(detections)
        matched_tracks: set[int] = set()

        for det in unmatched_dets:
            dcx, dcy = _polygon_centroid(det.polygon)
            best_track_idx: int | None = None
            best_dist: float = float("inf")

            for t_idx, track in enumerate(self.tracks):
                if t_idx in matched_tracks:
                    continue
                dist = math.hypot(dcx - track.cx, dcy - track.cy)
                if dist < best_dist and dist <= self.match_dist_px:
                    best_dist = dist
                    best_track_idx = t_idx

            if best_track_idx is not None:
                self.tracks[best_track_idx].update(det)
                matched_tracks.add(best_track_idx)
            else:
                # New vehicle entering the field of view
                new_track = TrackedVehicle(det)
                self.tracks.append(new_track)
                matched_tracks.add(len(self.tracks) - 1)

        # Handle missed tracks
        surviving_tracks: list[TrackedVehicle] = []
        for t_idx, track in enumerate(self.tracks):
            if t_idx not in matched_tracks:
                track.miss_count += 1
                if track.miss_count <= self.max_miss_frames:
                    surviving_tracks.append(track)
            else:
                surviving_tracks.append(track)

        self.tracks = surviving_tracks

        # Return detections sorted left-to-right for consistent numbering
        self.tracks.sort(key=lambda t: t.cx)
        results: list[Detection] = []
        for i, t in enumerate(self.tracks, start=1):
            d = t.detection
            # Keep consistent CAR-01, CAR-02 left-to-right ID
            stable_det = Detection(
                vehicle_id=f"CAR-{i:02d}",
                polygon=d.polygon,
                angle_deg=d.angle_deg,
                confidence=d.confidence,
                plate_hint=d.plate_hint,
                plate_conf=d.plate_conf,
                polygon_px=d.polygon_px,
            )
            t.detection = stable_det
            results.append(stable_det)

        return results

    def reset(self) -> None:
        self.tracks = []
        self.next_vehicle_idx = 1
