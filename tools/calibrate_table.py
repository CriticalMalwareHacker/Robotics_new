"""Manual table calibration: px corners + slot polys -> slots.json (cm).

The mat has no printed ArUco markers yet, so corners are passed explicitly
(measure once, re-run when the camera moves). Slot polygons are drawn in
image pixels and converted to centimetres via the corner homography.

Example (3 vertical bays, axis 90 deg):
    py tools/calibrate_table.py --image mat_v2.jpg \\
        --corners 175,105 1130,140 1085,650 110,665 \\
        --mat-width-cm 60 --mat-height-cm 45 \\
        --slot A1:175,105,450,122,432,655,110,665 \\
        --slot A2:450,122,772,132,762,652,432,655 \\
        --slot A3:772,132,1130,140,1085,650,762,652 \\
        --slot-angle 90 --out-preview calibration_check.jpg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "backend" / "services" / "parking" / "config" / "slots.json"


def parse_pt(s: str) -> list[float]:
    x, y = s.split(",")
    return [float(x), float(y)]


def parse_slot(s: str) -> tuple[str, list[list[float]]]:
    name, pts = s.split(":", 1)
    flat = [float(v) for v in pts.split(",")]
    if len(flat) < 6 or len(flat) % 2:
        raise ValueError(f"slot {name!r} needs >=3 x,y pairs")
    poly = [[flat[i], flat[i + 1]] for i in range(0, len(flat), 2)]
    return name, poly


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Calibrate parking mat to cm")
    ap.add_argument("--image", required=True)
    ap.add_argument("--corners", nargs=4, required=True,
                    help="TL TR BR BL in px as x,y (4 args)")
    ap.add_argument("--mat-width-cm", type=float, required=True)
    ap.add_argument("--mat-height-cm", type=float, required=True)
    ap.add_argument("--slot", action="append", default=[],
                    help="ID:x1,y1,x2,y2,... in px (repeatable)")
    ap.add_argument("--slot-angle", type=float, default=90.0)
    ap.add_argument("--restricted", action="append", default=[],
                    help="slot ID flagged no-parking (repeatable)")
    ap.add_argument("--out-preview", default="calibration_check.jpg")
    args = ap.parse_args(argv)

    img = cv2.imread(args.image)
    if img is None:
        print(f"ERROR: cannot read {args.image}")
        return 1
    h_img, w_img = img.shape[:2]

    src = np.asarray([parse_pt(c) for c in args.corners], dtype=np.float32)
    dst = np.asarray([[0, 0], [args.mat_width_cm, 0],
                      [args.mat_width_cm, args.mat_height_cm],
                      [0, args.mat_height_cm]], dtype=np.float32)
    h = cv2.getPerspectiveTransform(src, dst)

    slots = []
    for spec in args.slot:
        name, poly_px = parse_slot(spec)
        arr = np.asarray(poly_px, dtype=np.float32).reshape(-1, 1, 2)
        cm = cv2.perspectiveTransform(arr, h).reshape(-1, 2)
        slots.append({
            "slot_id": name,
            "polygon": [[round(float(x), 2), round(float(y), 2)] for x, y in cm],
            "angle_deg": args.slot_angle,
            "restricted": name in set(args.restricted),
        })

    cfg = {
        "_note": ("Manual corner calibration. RE-MEASURE mat border if "
                  "mat-width/height-cm are estimates; re-run this tool after "
                  "any camera move."),
        "units": "cm",
        "mat_size": [args.mat_width_cm, args.mat_height_cm],
        "image_size": [w_img, h_img],
        "corners_px_TL_TR_BR_BL": src.tolist(),
        "homography_px_to_cm": h.tolist(),
        "slots": slots,
    }
    OUT.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"WROTE: {OUT} ({len(slots)} slots)")

    # overlay preview in px for visual check
    for spec in args.slot:
        name, poly_px = parse_slot(spec)
        pts = np.asarray(poly_px, dtype=np.float32).astype(int)
        cv2.polylines(img, [pts], True, (0, 200, 0), 2)
        cv2.putText(img, name, (int(pts[:, 0].min()) + 6, int(pts[:, 1].min()) + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 0), 2, cv2.LINE_AA)
    cv2.imwrite(args.out_preview, img)
    print(f"PREVIEW: {args.out_preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
