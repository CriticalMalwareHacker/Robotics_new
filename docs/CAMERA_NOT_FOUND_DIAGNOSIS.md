# Camera Not Found — Frontend Diagnosis

Date: 2026-10-01
Symptom: frontend shows `Camera not found. Check the cable, then press Retry.`
Backend: `http://127.0.0.1:8000` reachable, `devices.camera = offline`

## 1. Where the message comes from

`frontend/src/hud/components/CameraFeed.jsx:51`

```jsx
'Camera not found. Check the cable, then press Retry.'
```

Shown when:

- `backendOnline == true` (so `/api/hud/state` is reachable), AND
- `cameraState != 'ok'` and `!= 'degraded'`

`cameraState` = `state?.devices?.camera` from `GET /api/hud/state`
(`frontend/src/hud/HudPage.jsx:77`, polled every 500 ms by
`frontend/src/hud/useHudState.js`).

Backend decides it in `app/api/hud_routes.py:_devices()`:

```python
meta_now = camera_manager.get_frame_meta()
if not meta_now.get("available"):
    cam = "offline"
elif (meta_now.get("brightness") or 0) < 3:
    cam = "degraded"
else:
    cam = "ok"
```

`available` = `_latest_jpeg is not None`. So "not found" really means
"background camera worker has not produced a JPEG yet", not necessarily
"no cable".

There are two separate viewers, both affected:

- HUD: `${API_URL}/api/parking/stream` (MJPEG) with fallback to
  `${API_URL}/api/parking/frame` (`frontend/src/hud/api.js:32-33`)
- Legacy `App.jsx:118` `CameraCapture`: `/api/camera/frame` + `/api/camera/capture`

## 2. Live evidence (this machine, Windows)

Backend was running (`uvicorn app.main:app`, `CAMERA_INDEX=1` in its env).

| Probe | Result |
|---|---|
| `GET /api/camera/list` | `idx0: 640x480 mean 0.2 (black)`, `idx1: 640x480 mean 136.0 (real cam)`, `idx2: absent`, `active_hint: 1` |
| `GET /api/camera/status` | `available:false, name:None, device_index:1, frames_flowing:false` |
| `GET /api/camera/frame` | `503 Camera frame not ready` |
| `GET /api/hud/state` | `devices.camera: offline`, `frame.available:false` |
| Direct OpenCV native `VideoCapture(1)` | `640x480 mean ~181` — works |
| Direct OpenCV `VideoCapture(1)` + force `1280x720` | `1280x720 mean 0.0` — black |
| `VideoCapture(0, CAP_V4L2)` on Windows | `isOpened() == False` |

Conclusion: the physical camera (index 1) is present and bright at its
native `640x480`, but goes black when forced to `1280x720`.

## 3. Root causes

### 3.1 Forced 1280x720 turns this camera black (main bug)

`app/services/camera.py:_open_capture()` did:

```python
cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
if not cap.isOpened():
    cap = cv2.VideoCapture(dev_idx)
cap.set(WIDTH, 1280); cap.set(HEIGHT, 720); cap.set(FPS, 30)
```

The worker then discards every frame with `mean < 0.5`:

```python
if not ret or frame is None or float(frame.mean()) < 0.5:
    bad += 1; continue
```

Since HD mode reads `mean 0.0` forever, `_latest_jpeg` stays `None`,
all frame endpoints return 503, HUD stays `offline`.

`/api/camera/list` does **not** set resolution, which is why it saw
bright frames while the worker saw only black.

### 3.2 `CAP_V4L2` is Linux-only

On Windows the first open always fails, adding seconds of delay before
the fallback open. Fixed by only trying `CAP_V4L2` on Linux.

### 3.3 Warmup / timeout mismatch

Measured cold-open time on this laptop: ~2.5–4 s to first frame
(DSHOW warmup + resolution negotiation).

- `get_latest_jpeg()` only waited `15 x 0.08 s = 1.2 s` → 503 during warmup
- `get_frame_meta()` returns immediately → first ~5 HUD polls (500 ms)
  report `offline`, so the user sees "not found" instantly with no
  "starting…" distinction.

### 3.4 Linux-only presence check

```python
exists = Path(f"/dev/video{idx}").exists()  # always False on Windows
available = exists or flowing
name = "None" if not exists and not flowing
```

On Windows the status says `None` until the first frame flows, which is
misleading during warmup.

### 3.5 Stale / competing backends hid the fix

Multiple `uvicorn app.main:app` processes were bound to port 8000
(PIDs 13332, 19836, 29612 observed). Old workers hold the camera
exclusively on Windows, so a new process gets `isOpened() == False`
on the same index. Always keep exactly one backend on 8000.

## 4. Fix applied

File: `app/services/camera.py`

1. `_open_capture()`:
   - only use `CAP_V4L2` on Linux, direct open on Windows/macOS
   - try HD, read-probe 10 frames; if still black (`mean < 0.5`),
     release and reopen at native resolution + 10 warmup reads
2. `get_latest_jpeg()`: wait up to ~5 s (`50 x 0.1 s`) instead of 1.2 s
   to cover cold open.

Standalone verification after fix (`CAMERA_INDEX=1`):

```text
dev 1
m1 available False (cold, expected)
jpeg 100916 bytes
meta2 {id: 1, width: 1280, height: 720, available: True, brightness: 175.2}
```

A single backend was restarted on port 8000 with `CAMERA_INDEX=1`
(PID 4424 at time of writing).

## 5. How to verify now

```powershell
$env:CAMERA_INDEX='1'
py -3.13 tools/test_camera.py --mode api --url http://127.0.0.1:8000/api/camera/frame --count 2
```

Expect HTTP 200 / JPEG bytes, then:

- `GET /api/camera/status` → `frames_flowing:true`
- `GET /api/hud/state` → `devices.camera: ok`, `frame.available:true`
- HUD `/hud` shows live video after ~5 s (hard refresh; Vite bakes
  `VITE_API_URL` at start — local dev keeps it empty so `/api` goes
  through the Vite proxy at `127.0.0.1:8000`).

If it still shows offline: kill duplicate uvicorns so only one holds
the camera, confirm no other app (browser tab, video call) holds index 1,
and re-check `GET /api/camera/list` for the brightest index.

## 6. Suggested follow-ups (not yet done)

- HUD: add a third `starting` state (e.g. first 5 s / `frame.id==0`)
  showing `Starting camera…` instead of `Camera not found`.
- Backend: auto-pick the brightest of indexes 0–2 on Windows when
  `CAMERA_INDEX` is unset, instead of defaulting to 0.
- Backend: make `/api/camera/status` call `ensure_started()` or document
  that only `/frame` / `/hud/state` warm the worker.
- Frontend `App.jsx` uses bare `/api/...` while HUD uses `API_URL` prefix;
  unify on the shared client so Vercel+tunnel deployments behave the same.
