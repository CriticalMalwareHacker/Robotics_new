# Handoff: HUD Camera — "Not Found" + Overlay Sizing/Boxing

Date: 2026-10-01. Machine: Windows laptop, backend `uvicorn app.main:app :8000`,
frontend Vite HUD (`/hud`). Physical camera is at **index 1**
(`CAMERA_INDEX=1`); index 0 is black/virtual, index 2 absent.

## Status at handoff

- Code fixes for both issues are applied (7 files, uncommitted — see §4).
- `pytest tests/test_detector.py tests/test_hud.py tests/test_parking_geometry.py
  tests/test_camera_frame.py` → **24 passed**.
- Scaling math verified numerically (see §3).
- Backend on :8000 is up but `devices.camera` reads `offline` right now
  (15:44 UTC) — the camera worker is flaky under competing processes (see §5,
  step 1: kill duplicate uvicorns, keep exactly one with `CAMERA_INDEX=1`).
- Earlier full-success run exists: standalone `CAMERA_INDEX=1` produced
  `jpeg 100916 bytes, 1280x720, brightness 175.2`, and the HUD showed
  `Camera · Ok` with live video (user screenshot).

---

## Issue 1 — "Camera not found. Check the cable, then press Retry."

### Where the message comes from

- `frontend/src/hud/components/CameraFeed.jsx:51` — shown when backend is
  reachable but `devices.camera` from `GET /api/hud/state` is neither
  `ok` nor `degraded`.
- Decided in `app/api/hud_routes.py:_devices()` via
  `camera_manager.get_frame_meta()["available"]`
  (= "has the worker produced a JPEG yet"). So it means "no frames flowing",
  not "no cable".
- Two viewers affected: HUD (`/api/parking/stream` → fallback
  `/api/parking/frame`) and legacy `App.jsx` `CameraCapture`
  (`/api/camera/frame` + `/api/camera/capture`).

### Root causes found (all verified live)

1. **Forced 1280×720 turns this camera black.** Old
   `app/services/camera.py:_open_capture()` set 1280×720 unconditionally.
   Probed: native `VideoCapture(1)` → `640×480 mean ~181` (good);
   after forcing 1280×720 → `mean 0.0` (black). The worker discards
   `mean < 0.5` frames forever → `_latest_jpeg` stays `None` → every frame
   endpoint 503s → HUD `offline`. (`/api/camera/list` doesn't set
   resolution, which is why it saw bright frames while the worker saw black.)
2. **`CAP_V4L2` on Windows always fails** (`isOpened()==False`), adding
   seconds before the fallback open.
3. **Warmup/timeout mismatch.** Cold open needs ~2.5–4 s; old
   `get_latest_jpeg()` waited only 1.2 s, and `get_frame_meta()` returns
   instantly, so the first ~5 HUD polls (500 ms) report `offline`.
4. **Linux-only presence check** (`Path("/dev/videoX").exists()`, always
   False on Windows) → status `name: "None"` during warmup.
5. **Duplicate backends.** Several `uvicorn app.main:app` processes were
   bound to :8000 at once; on Windows the camera open is exclusive, so a
   second process starves.

### Fix (in `app/services/camera.py`)

- `_open_capture()`: try `CAP_V4L2` on Linux only; try HD, probe 10 frames,
  and if still black reopen at **native resolution** + warmup reads.
- `get_latest_jpeg()`: wait up to ~5 s (`50 × 0.1 s`) for cold open.

Prior write-up: `docs/CAMERA_NOT_FOUND_DIAGNOSIS.md`.

---

## Issue 2 — Overlay boxes overflow the video + pillarbox bars (screenshot)

### Symptom

Live video renders (640×480, footer confirms), but slot boxes A1/A2/A3 run
past the image's right edge into the black side bars.

### Root causes

1. **Calibration/frame resolution mismatch (the boxing bug).**
   `backend/services/parking/config/slots.json` is calibrated at
   `image_size [1280, 720]` (mat corners e.g. x up to 1130). The camera now
   serves **640×480** (native fallback from Issue-1 fix). All three
   cm→px render paths used the 1280-space homography inverse unscaled:
   - `app/api/hud_routes.py:_cm_to_px()` (client SVG overlay),
   - `backend/services/parking/annotator.py:_to_px()` (boxes baked into
     `/api/parking/frame` JPEG),
   - and symmetrically the detector's px→cm path
     (`vehicle_detector.ClassicalDetector` with 1280-space `H` + `roi_px`
     corners up to x=1130) plus 1280-tuned `MIN_AREA_PX=8000` /
     `MIN_LONG_SIDE_PX=60` (at 640×480 cars are ~1/3 the pixels, so real
     cars risk being filtered out).
   
   Verified numerically: A1 maps to `[[175,105],[450,122],[432,655],[110,665]]`
   in 1280-space — x=1130 overflows a 640-wide image. After scaling:
   `[[88,70],[225,81],[216,437],[55,443]]` — inside the frame. (Note: x
   scales ×0.5, y ×0.667 — 16:9 vs 4:3 aspect differs, so this is the
   correct affine approximation; a re-calibration at 640×480 is the
   exact fix, see §6.)
2. **Pillarbox bars (the sizing part).** Container uses `w-full` +
   `aspect-ratio` + `maxHeight: 62vh`. When the viewport clamps height, the
   box stays full-width → wider than the image → black bars left/right in
   both `<img object-contain>` and the SVG (they stay aligned with each
   other; the bars themselves are harmless but ugly).

### Fix

- `vehicle_detector.py`: `ClassicalDetector(..., calib_size=(1280,720))`;
  `detect()` scales `H` per frame (`H_frame = H_calib @ diag(cw/fw, ch/fh)`),
  scales `roi_px` to frame pixels, scales area thresholds by pixel-count
  ratio and side threshold by its sqrt. Identical sizes → exact no-op
  (existing 1280×720 tests/fixtures unaffected — 24 passed).
- `monitor.py:load_detector()`: passes `calib_size` from `slots.json`
  `image_size`; also removed a duplicated config-load block.
- `annotator.py`: `_to_px(..., scale)` + `annotate(..., calib_size=...)`
  scales rendered boxes to the actual frame; `parking_routes.py` passes
  `cfg["image_size"]`.
- `hud_routes.py`: `_cm_to_px(..., scale)`; `hud_state()` computes
  `scale = (meta.w/calib.w, meta.h/calib.h)`, falling back to calib size
  when meta is 0 (camera offline → old 1280 coords, harmless since nothing
  is drawn while offline).
- `frontend/src/hud/components/CameraFeed.jsx`: container gets
  `maxWidth: calc(62vh * w / h)` so the box keeps the image aspect when
  height-clamped → no pillarbox bars.

---

## §4 Changed files (all uncommitted)

```
M app/api/hud_routes.py
M app/api/parking_routes.py
M app/services/camera.py
M backend/services/parking/annotator.py
M backend/services/parking/monitor.py
M backend/services/parking/vehicle_detector.py
M frontend/src/hud/components/CameraFeed.jsx
```

Docs added earlier: `docs/CAMERA_NOT_FOUND_DIAGNOSIS.md` (Issue 1 detail).

## §5 Verify live (do in this order)

1. **Exactly one backend, with the right camera:**
   ```powershell
   py -3.13 -c "import psutil; [print(p.pid) or p.kill() for p in psutil.process_iter(['pid']) if 'uvicorn app.main' in ' '.join(p.cmdline())]"
   $pyexe = (Get-Command py).Source; $env:CAMERA_INDEX = '1'
   Start-Process -FilePath $pyexe -ArgumentList '-3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
   ```
   Close anything else holding the camera (browser tabs, video calls).
2. **Warm up, then check** (allow ~10 s):
   ```powershell
   py -3.13 tools/test_camera.py --mode api --url http://127.0.0.1:8000/api/camera/frame --count 2
   ```
   Expect HTTP 200 + JPEG bytes (not 503).
3. **HUD state must show scaled boxes inside the frame:**
   ```powershell
   py -3.13 -c "import urllib.request, json; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/hud/state', timeout=20)); print(d['devices']); print(d['frame']); print(d['parking']['slots'])"
   ```
   Expect `devices.camera: ok`, `frame ~640×480 available True`, and every
   `polygon_px` point with `0 <= x <= frame.width`, `0 <= y <= frame.height`.
4. **Frontend:** hard-refresh `/hud` (Vite bakes `VITE_API_URL` at start;
   local dev keeps it empty so `/api` uses the Vite proxy). Boxes should sit
   on the video with no side bars; if the laptop camera looks at the desk
   instead of the parking mat, boxes will still be geometrically consistent
   but semantically meaningless until pointed at the mat.

## §6 Follow-ups (not done)

- Recalibrate `slots.json` at 640×480 (re-run the corner-calibration tool
  against a 640×480 capture) to remove the 16:9→4:3 aspect approximation.
- HUD: add a `starting` state (first ~5 s / `frame.id==0`) showing
  "Starting camera…" instead of "Camera not found".
- Auto-pick brightest of indexes 0–2 on Windows when `CAMERA_INDEX` unset.
- Unify `App.jsx` (bare `/api/...`) with the HUD `API_URL` client for
  Vercel+tunnel deploys.
