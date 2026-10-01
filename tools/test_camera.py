"""Phase 1 camera probe: Hikvision USB camera -> OpenCV -> JPEG (+ API mode).

Usage (laptop or Pi):
    py -3.13 tools/test_camera.py --out frame.jpg
    py -3.13 tools/test_camera.py --out frame.jpg --mock        # force synthetic frame
    py -3.13 tools/test_camera.py --mode api --url http://<pi>:8000/api/camera/frame --out test.jpg

Behavior:
- direct mode opens cv2.VideoCapture(index), requests --width x --height,
  grabs --frames frames to measure FPS, saves the last frame to --out.
- If no camera is found (laptop) or cv2 is missing, a synthetic MOCK frame
  is generated so the script and tests pass with no hardware attached.
- api mode GETs an /api/camera/frame URL N times and reports latency/FPS.
- Prints BACKEND / RESOLUTION / FPS / SAVED lines for the Phase 1 gate.
- Exit 0 on saved frame (live or mock). Exit 2 only on bad arguments or
  unwriteable output path. Never raises on missing hardware (fail-safe).
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path


def make_mock_frame_bgr(width: int = 640, height: int = 480):
    """Return a synthetic BGR frame (numpy) so laptop runs need no camera."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    img = np.full((height, width, 3), 32, dtype=np.uint8)
    # draw a fake "table" + slot lines + label so resolution is verifiable
    cv2.rectangle(img, (40, 40), (width - 40, height - 40), (200, 200, 200), 2)
    for i in range(1, 4):
        x = 40 + i * (width - 80) // 4
        cv2.line(img, (x, 40), (x, height - 40), (200, 200, 200), 1)
    cv2.putText(img, "MOCK FRAME (no camera)", (60, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(img, f"{width}x{height}", (60, height // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def save_bgr_as_jpeg(frame_bgr, out_path: Path) -> Path:
    import cv2

    ok, jpeg = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("cv2.imencode failed")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(jpeg.tobytes()))
    return out_path


def probe_direct(index: int, width: int, height: int, frames: int, out: Path) -> dict:
    """Open local USB camera directly. Returns result dict; falls back to mock."""
    try:
        import cv2
    except ImportError as exc:
        frame = None
        print(f"BACKEND: mock (cv2 missing: {exc})")
        mock = make_mock_frame_bgr(width, height)
        if mock is None:  # cv2 truly missing -> Pillow fallback
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (width, height), (32, 32, 32))
            d = ImageDraw.Draw(img)
            d.rectangle([40, 40, width - 40, height - 40], outline=(200, 200, 200))
            d.text((60, height // 2), "MOCK FRAME (no cv2)", fill=(0, 255, 0))
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out, "JPEG", quality=90)
            h, w = height, width
        else:
            save_bgr_as_jpeg(mock, out)
            h, w = mock.shape[:2]
        print(f"RESOLUTION: {w}x{h}")
        print("FPS: n/a (mock)")
        print(f"SAVED: {out}")
        print("SOURCE: MOCK")
        return {"source": "mock", "width": w, "height": h, "fps": 0.0, "out": str(out)}

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"BACKEND: mock (VideoCapture({index}) not opened — no camera on this host)")
        mock = make_mock_frame_bgr(width, height)
        save_bgr_as_jpeg(mock, out)
        h, w = mock.shape[:2]
        print(f"RESOLUTION: {w}x{h}")
        print("FPS: n/a (mock)")
        print(f"SAVED: {out}")
        print("SOURCE: MOCK")
        return {"source": "mock", "width": w, "height": h, "fps": 0.0, "out": str(out)}

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or width)
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or height)
        backend = cap.getBackendName() if hasattr(cap, "getBackendName") else "opencv"
        print(f"BACKEND: {backend} (index {index}, requested {width}x{height})")

        last = None
        t0 = time.time()
        got = 0
        for _ in range(max(1, frames)):
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            last = frame
            got += 1
        dt = time.time() - t0
        fps = (got / dt) if dt > 0 else 0.0

        if last is None:
            print("BACKEND: mock (camera opened but returned no frames)")
            mock = make_mock_frame_bgr(width, height)
            save_bgr_as_jpeg(mock, out)
            h, w = mock.shape[:2]
            print(f"RESOLUTION: {w}x{h}")
            print("FPS: n/a (mock)")
            print(f"SAVED: {out}")
            print("SOURCE: MOCK")
            return {"source": "mock", "width": w, "height": h, "fps": 0.0, "out": str(out)}

        h, w = last.shape[:2]
        save_bgr_as_jpeg(last, out)
        print(f"RESOLUTION: {w}x{h} (actual; requested {actual_w}x{actual_h})")
        print(f"FPS: {fps:.1f} ({got}/{max(1, frames)} frames in {dt:.2f}s)")
        print(f"SAVED: {out}")
        print("SOURCE: LIVE")
        return {"source": "live", "width": w, "height": h, "fps": fps, "out": str(out)}
    finally:
        cap.release()


def fetch_api(url: str, count: int, out: Path, timeout: float) -> dict:
    import cv2
    import numpy as np

    latencies: list[float] = []
    payload: bytes | None = None
    for _ in range(max(1, count)):
        t0 = time.time()
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned HTTP {resp.status}")
            payload = resp.read()
        latencies.append(time.time() - t0)
    assert payload is not None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    arr = np.frombuffer(payload, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is not None:
        h, w = frame.shape[:2]
        print(f"RESOLUTION: {w}x{h}")
    else:
        print("RESOLUTION: unknown (payload not decodable as JPEG)")
        h, w = 0, 0
    avg = sum(latencies) / len(latencies)
    fps = (1.0 / avg) if avg > 0 else 0.0
    print(f"BACKEND: http ({url})")
    print(f"FPS: {fps:.1f} (avg latency {avg * 1000:.0f} ms over {len(latencies)} requests)")
    print(f"SAVED: {out} ({len(payload)} bytes)")
    print("SOURCE: LIVE-API")
    return {"source": "live-api", "width": w, "height": h, "fps": fps, "out": str(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 Hikvision USB camera probe")
    parser.add_argument("--out", default="frame.jpg", help="output JPEG path")
    parser.add_argument("--mode", choices=["direct", "api"], default="direct")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/camera/frame",
                        help="API frame URL (for --mode api)")
    parser.add_argument("--index", type=int, default=0, help="cv2 device index")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--frames", type=int, default=30, help="frames for FPS estimate")
    parser.add_argument("--count", type=int, default=5, help="API requests for FPS estimate")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--mock", action="store_true", help="force synthetic frame")
    args = parser.parse_args(argv)

    out = Path(args.out)
    try:
        if args.mock:
            mock = make_mock_frame_bgr(args.width, args.height)
            if mock is None:
                print("BACKEND: mock requested but cv2/numpy missing and no fallback")
                return 2
            save_bgr_as_jpeg(mock, out)
            h, w = mock.shape[:2]
            print("BACKEND: mock (forced by --mock)")
            print(f"RESOLUTION: {w}x{h}")
            print("FPS: n/a (mock)")
            print(f"SAVED: {out}")
            print("SOURCE: MOCK")
            return 0
        if args.mode == "api":
            fetch_api(args.url, args.count, out, args.timeout)
            return 0
        probe_direct(args.index, args.width, args.height, args.frames, out)
        return 0
    except Exception as exc:  # fail-safe: never traceback on missing hardware
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
