import pytest
from backend.services.parking.models import Detection, Slot
from backend.services.parking.trackers import BayGridTracker, VehicleTracker


def test_bay_grid_tracker_persistence():
    tracker = BayGridTracker(max_hold_frames=3)
    bays = [
        Slot(slot_id="BAY-1", polygon=[[10, 10], [50, 10], [50, 100], [10, 100]]),
        Slot(slot_id="BAY-2", polygon=[[55, 10], [95, 10], [95, 100], [55, 100]]),
    ]
    lines = [(10, 10, 10, 100), (50, 10, 50, 100), (95, 10, 95, 100)]

    # Frame 1: Valid bays detected
    out_bays, out_lines = tracker.update(bays, lines)
    assert len(out_bays) == 2
    assert len(out_lines) == 3

    # Frame 2: Transient blur -> 0 bays detected
    out_bays2, out_lines2 = tracker.update([], [])
    assert len(out_bays2) == 2
    assert len(out_lines2) == 3

    # Frame 3: Transient blur continues
    out_bays3, _ = tracker.update([], [])
    assert len(out_bays3) == 2

    # Frame 4: 3rd hold frame
    out_bays4, _ = tracker.update([], [])
    assert len(out_bays4) == 2

    # Frame 5: Hold expired -> returns empty
    out_bays5, _ = tracker.update([], [])
    assert len(out_bays5) == 0


def test_vehicle_tracker_persistence_and_ocr():
    tracker = VehicleTracker(max_miss_frames=1, match_dist_px=50.0)

    # Frame 1: Car 1 detected with plate OCR
    det1 = Detection(
        vehicle_id="CAR-01",
        polygon=[[100, 100], [150, 100], [150, 200], [100, 200]],
        angle_deg=90.0,
        confidence=0.95,
        plate_hint="KA01AB1234",
        plate_conf=0.92,
    )
    tracked1 = tracker.update([det1])
    assert len(tracked1) == 1
    assert tracked1[0].plate_hint == "KA01AB1234"

    # Frame 2: Car 1 moved slightly (102, 102), but OCR failed (plate_hint=None)
    det2 = Detection(
        vehicle_id="CAR-01",
        polygon=[[102, 102], [152, 102], [152, 202], [102, 202]],
        angle_deg=90.0,
        confidence=0.94,
        plate_hint=None,
        plate_conf=None,
    )
    tracked2 = tracker.update([det2])
    assert len(tracked2) == 1
    # Plate was preserved from frame 1
    assert tracked2[0].plate_hint == "KA01AB1234"
    assert tracked2[0].plate_conf == 0.92

    # Frame 3: Car 1 missed for 1 frame (grace period)
    tracked3 = tracker.update([])
    assert len(tracked3) == 1
    assert tracked3[0].plate_hint == "KA01AB1234"

    # Frame 4: Car 1 missed for 2nd frame -> expired
    tracked4 = tracker.update([])
    assert len(tracked4) == 0
