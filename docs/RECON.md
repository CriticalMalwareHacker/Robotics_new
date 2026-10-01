# PrintSensei Parking Robot — Phase 0 Recon (RECON.md)

Date: 2026-10-01
Branch intent: `robotics` (created at end of Phase 0, not pushed to `main`)
Scope: read-only reconnaissance. No existing file was modified. Only this new file
`docs/RECON.md` was added.

> Note on brief vs repo: the build brief refers to a context file
> `PrintSensei_Claude_Handoff.md`. That file does **not** exist in the repo
> (checked root + glob `**/*handoff*`, case-insensitive on Windows).
> The repo contains `PrintSensei_Printer_Implementation_Handoff.md` (877 lines,
> ESC/POS verified path) and `IMPLEMENTATION_SUMMARY.md` (62 lines, outdated —
> still describes TSPL). Recon below uses the actual repo state on disk.

---

## 1. Directory tree (2 levels deep)

```text
AI-Robotics_PrintSensei/
  app/
    constants/  core/  enums/  hardware/  models/
    renderer/  schemas/  services/  state/
    main.py  routers.py  startup.py  __init__.py
  backend/
    core/  engines/  renderers/  services/  tests/
    __init__.py
  frontend/
    src/ (App.jsx, main.jsx, styles.css)
    index.html  package.json  package-lock.json  vite.config.js
  shared/
    config.py  logging_config.py  __init__.py
  infrastructure/
    database.py  database_models.py  __init__.py
  tests/
    test_main.py  test_phase_four_simulator.py
    test_phase_three_renderer.py  test_phase_two.py
    test_printer.py
  data/captures/
  diagram_images/ (+ uploads/)
  Documentation/ (+ Ressearch_Papers/, PDF, REF_IMAGE.png)
  diagram_images/ (generated output, gitignored)
  .env.example  .gitignore  requirements.txt
  README.md  IMPLEMENTATION_SUMMARY.md
  PrintSensei_Printer_Implementation_Handoff.md
  run_robot.py
```

Third level (only where load-bearing for the robot project):

```text
app/services/       audio_recorder.py  camera.py  history.py  printer.py
app/hardware/       display/  input/  menu/  simulator/  events.py
app/hardware/simulator/  __init__.py  simulator.py
app/renderer/       canvas.py  fonts.py  image_utils.py  qr.py  renderer.py  templates/
app/state/          state_machine.py
app/enums/          device_state.py  input_type.py  intent.py  label_type.py  status.py
app/models/         label_data.py  print_request.py
app/schemas/        render.py  simulate.py
backend/services/   ai/  image/  speech/  vision/
backend/engines/diagram/  service.py (referenced by routers.py)
infrastructure/     database.py (init_db), database_models.py
frontend/src/       App.jsx (~1008 lines, LCD-style UI state machine)
```

Git state at recon time:

```text
branch: main
HEAD: 408f13d docs: document Hikvision USB webcam, smart LED lifecycle, and USB mic recording pipeline
working tree: clean (git status --short empty, apart from untracked docs/ added in this phase)
```

---

## 2. How `app/main.py` mounts routers and starts services

File: `app/main.py` (33 lines). Full content verified by read.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routers import router
from app.startup import initialize_app
from shared.config import APP_NAME, APP_VERSION

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(router)          # <-- single monolithic router, no prefix
Path("diagram_images").mkdir(exist_ok=True)
Path("generated_labels").mkdir(exist_ok=True)
app.mount("/generated-images", StaticFiles(directory="diagram_images"), ...)
app.mount("/generated_labels", StaticFiles(directory="generated_labels"), ...)
app.mount("/generated-labels", StaticFiles(directory="generated_labels"), ...)

@app.on_event("startup")
def startup_event() -> None:
    initialize_app()
```

`app/startup.py` (9 lines):

```python
def initialize_app() -> None:
    init_db()
    logger.info("PrintSensei startup complete")
```

Key facts for the robot project:

- There is **one** router object (`app.routers.router`, an `APIRouter()` with no
  prefix). All routes live in `app/routers.py` (369 lines).
- No router splitting yet. New robot/parking routers must be **new files**
  (e.g. `app/api/robot_routes.py`, `app/api/parking_routes.py`) and mounted
  additively via `app.include_router(...)` in `app/main.py`. That is the one
  small additive edit to `app/main.py`.
- Startup does only `init_db()` (SQLite). It does **not** start camera,
  printer, serial, or background monitor loops. Camera is lazily started on
  first `/api/camera/frame` request (see §3). Fail-safe behavior (§8 of brief)
  is therefore natural: missing hardware never blocks boot.
- CORS is fully open (`allow_origins=["*"]`). No auth on any route.
- Deprecated `@app.on_event("startup")` is used (still works on installed
  FastAPI 0.141.1, but lifespan handler is the future upgrade path — out of
  scope for robot phases).
- Config comes from `shared/config.py` via env (`APP_NAME`, `APP_VERSION`,
  `MODE`, `HARDWARE_MODE` default `"pc"`, `DATABASE_URL`,
  `HOST` default `127.0.0.1`, `PORT` default `8000`).

Existing routes in `app/routers.py` (do not break):

```text
GET  /                                  HTML "PrintSensei is Running"
GET  /health
GET  /api/history
POST /api/print                         HardwarePrintRequest -> print_label()
POST /voice/transcribe
POST /api/voice/start_record | stop_record | cancel_record
GET  /api/system/status                 wifi/printer/camera/system telemetry
GET  /api/camera/status
GET  /api/camera/frame                  <-- already exists, reuse for Phase 1
POST /api/camera/capture
POST /api/camera/release
POST /simulate   POST /render   POST /study/generate
```

---

## 3. `app/services/camera.py` — exact public API and backend

File: `app/services/camera.py` (128 lines). Backend is **OpenCV VideoCapture
only**. There is **no Picamera2** code in the repo today.

Public surface:

| Symbol | Signature | Meaning |
|---|---|---|
| `CameraManager` | `class CameraManager` | USB-camera session manager, thread-safe via `threading.Lock` |
| `CameraManager.ensure_started()` | `() -> None` | Lazily spawns background worker thread if not alive; updates last-access time |
| `CameraManager.get_latest_jpeg()` | `() -> bytes \| None` | Ensure worker running, wait up to ~1.2–1.5 s (15×80 ms) for first frame, return latest cached JPEG bytes (quality 80). Returns `None` if camera never yields a frame |
| `CameraManager.capture_photo()` | `() -> tuple[bool, str, str]` | Returns `(success, data_uri, message)`; data URI is `data:image/jpeg;base64,...`. Side effect: sets `_last_access = now - 2.0` so worker auto-releases ~1 s later |
| `CameraManager.release_now()` | `() -> None` | Stops worker, releases `cv2.VideoCapture` (LED back to RED) |
| `camera_manager` | module singleton `CameraManager()` | Used by `app/routers.py` |
| `get_camera_status()` | `() -> dict[str, str \| bool \| int]` | Returns `{available, name, device_index}`; `available` = `Path(/dev/video<idx>).exists()` |

Backend details (how to get a frame):

- `_get_device_index()`: first existing path among `/dev/video0,1,2`, else `0`.
- Worker: `cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)`, fallback plain
  `cv2.VideoCapture(dev_idx)`. Sets `CAP_PROP_FRAME_WIDTH=1280`,
  `CAP_PROP_FRAME_HEIGHT=720`, `CAP_PROP_FPS=30`.
- Loop: `cap.read()` → `cv2.imencode(".jpg", frame, [IMWRITE_JPEG_QUALITY, 80])`;
  caches both `_latest_jpeg: bytes` and `_latest_frame_bgr` (raw BGR `ndarray`,
  **not exposed** by any public method today — Phase 1 / parking code will need
  either a new accessor returning the BGR array or decode the JPEG).
- Auto-release: if `time.time() - _last_access > 3.0 s`, worker breaks and
  releases the V4L2 handle (physical LED RED on the Hikvision camera).
  Every `get_latest_jpeg()` / `ensure_started()` refreshes `_last_access`.
- `GET /api/camera/frame` calls `camera_manager.get_latest_jpeg()` and returns
  `Response(content=jpeg, media_type="image/jpeg")` with no-cache headers;
  503 if `None`. `GET /api/camera/status` calls `get_camera_status()`.

Implications for Phase 1:

- Reuse `camera_manager` and `GET /api/camera/frame` as-is; do **not** add a
  second capture path. Only additive work needed: `tools/test_camera.py`
  (OpenCV client pulling the HTTP endpoint + optional direct VideoCapture
  probe for laptop testing) and, if needed, a `get_latest_bgr()` accessor on
  `CameraManager` for vision (new method on existing class = small additive
  edit, or a wrapper in the new parking service that JPEG-decodes).
- Pi camera module path (Picamera2) does not exist; if the demo later uses the
  Pi Camera Module instead of USB, a Picamera2 backend must be added behind
  the same manager interface. Default stays USB (`VEHICLE_DETECTOR`-style env
  switch can select backend later).

---

## 4. `app/services/printer.py` + `/api/print` — exact verified path

File: `app/services/printer.py` (290 lines). This is the **verified working**
path. Brief rule 1 applies: reuse, do not rewrite, no TSPL.

Constants and config:

```python
THERMAL_PRINT_WIDTH_PX = 384   # 58 mm head, 203 DPI ≈ 8 dots/mm ≈ 48 mm printable
USBDEVFS_RESET = 21780 (0x5514)

@dataclass(frozen=True)
class PrinterConfig:
    device: str = os.getenv("PRINTER_DEVICE", "/dev/usb/lp0")
    cups_queue: str = os.getenv("CUPS_QUEUE", "POSIFLOW58D")
    use_cups: bool = os.getenv("PRINTER_USE_CUPS", "false") in {"1","true","yes"}
```

Public functions (exact signatures):

```python
def prepare_image_for_printing(image: Image.Image, target_width: int = 384) -> Image.Image
    # RGBA/LA/P+transparency -> white composite; resize proportionally (LANCZOS)
    # to width 384; L + Floyd-Steinberg to mode "1"; pad width to multiple of 8.

def pil_to_escpos_raster(image: Image.Image, target_width: int = 384) -> bytes
    # returns ESC @ (1B 40) + GS v 0 (1D 76 30 00 + xL xH yL yH) + packed bits + b"\n\n\n\n"
    # black (0 in mode "1") -> bit 1; white -> bit 0; MSB-first per byte.

def send_to_printer(payload: bytes, config: PrinterConfig | None = None) -> tuple[bool, str]
    # 1) PyUSB direct bulk transfer (finds 0456:0808, detach kernel, ESC @, 512 B
    #    paced chunks, halt-clear, stall-recovery via USBDEVFS_RESET + retry)
    # 2) direct device-node write to config.device (/dev/usb/lp0), 512 B chunks
    # 3) CUPS `lp -d <queue> -o raw` if `lp` exists
    # 4) simulated success if HARDWARE_MODE=="pc" or MOCK_PRINTER in {1,true}
    #    -> (True, "Simulated print (PC mode): ...")

def print_label(image: Image.Image, label_width_mm: int = 50,
                label_height_mm: int = 50, gap_mm: int = 2,
                config: PrinterConfig | None = None) -> tuple[bool, str]
    # THE function new ticket code must call. Encodes via pil_to_escpos_raster
    # (target 384) then send_to_printer. Ignores mm args for raster sizing
    # (kept for API compat); height is dynamic from the image aspect.
```

`/api/print` route (`app/routers.py` lines 28–68):

```python
class HardwarePrintRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=15_000_000)
    label_width_mm: int = 50 (10..120)
    label_height_mm: int = 50 (10..300)
    gap_mm: int = 2 (0..20)
    title/desc/mode/image_url: optional (for history)

@router.post("/api/print")
def print_hardware_label(payload: HardwarePrintRequest):
    # split data-URI prefix, b64decode(validate=True), PIL open+load
    # 422 on bad image; calls print_label(image, w, h, gap)
    # 502 on printer failure; on success add_history_entry(...) + {"status":"success"}
```

Confirmed output path:

```text
Pillow image -> prepare_image_for_printing (384 dots wide, 1-bit, pad to /8)
  -> pil_to_escpos_raster (ESC @ + GS v 0 header, MSB-first packing, +\n\n\n\n)
  -> send_to_printer: PyUSB bulk first, then /dev/usb/lp0, then CUPS raw, else PC simulation
Expected image width in dots: 384.  NEVER TSPL (TSPL prints as literal text on this unit).
```

Tests proving it: `tests/test_printer.py` (79 lines, 5 tests) — ESC @ + header
bytes (`1B 40 1D 76 30 00 30 00 64 00` for 384×100), size math
(`2+8+48*100+4`), bit-packing (`0b10000001`), endpoint success + 422 paths.
`IMPLEMENTATION_SUMMARY.md` is stale (still says TSPL `BITMAP`/`SIZE`/`GAP`);
ignore it — `printer.py` + `test_printer.py` + the Handoff doc are authoritative.

---

## 5. `run_robot.py` and `RobotSimulator` — what they do, reusability

`run_robot.py` (12 lines):

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    RobotSimulator().start(interactive=True)
```

`app/hardware/simulator/simulator.py` (219 lines) — `class RobotSimulator`:

- A **desktop LCD-menu simulator** for the stationary PrintSensei assistant.
  Coordinates `LCDSimulator` (display), `EventDispatcher`, `KeyboardMapper`,
  `Menu`, `LabelRenderer`, and `app.state.state_machine.StateMachine`
  (BOOTING→READY→MENU→LISTENING→PROCESSING→PREVIEW→PRINTING→DONE/ERROR).
- `start(interactive=True)` opens a local window and runs a timed boot
  animation; `interactive=False` renders one boot frame and finishes boot.
- Event handlers `_on_up/_on_down/_on_ok/_on_back`, `_generate_preview(action)`
  (builds sample `LabelData` for INVENTORY/STUDY/QR/PRODUCT and renders to a
  file), `_on_start_print` (timed progress-bar animation only — **no hardware
  I/O**), `_on_print_complete`, `_on_error`.
- No serial, no GPIO, no motors, no ultrasonic, no camera, no printer I/O.

Verdict for the parking robot:

- **Not reusable as a robot-motion interface.** It models a different device
  (stationary label kiosk UI) and a different state graph. Do not subclass or
  wire driving code through it.
- **Reusable as a pattern only:** the `StateMachine` with explicit
  `can_transition/transition_to` + event dispatcher is the right shape to copy
  for `robot/state_machine.py` with a new parking-robot `Enum`
  (BOOT/IDLE/PATROLLING/…/ERROR). Keep the two state machines separate files;
  do not merge graphs.
- `run_robot.py` stays untouched (manual desktop demo entry point). The
  parking robot gets its own entry/loop (monitor thread + auto state machine),
  not a flag inside `run_robot.py`.

---

## 6. Reuse / untouched / additive-edit plan

### REUSE as-is (import, do not copy or fork)

- `app/services/printer.py`: `print_label`, `pil_to_escpos_raster`,
  `prepare_image_for_printing`, `PrinterConfig`, `THERMAL_PRINT_WIDTH_PX=384`.
  Ticket code calls `print_label(Pillow_image)` and never opens
  `/dev/usb/lp0` itself.
- `app/services/camera.py`: `camera_manager.get_latest_jpeg()` (+
  `capture_photo`, `release_now`, `get_camera_status`) and the existing
  `GET /api/camera/frame|status` + `POST /api/camera/capture|release` routes.
- `backend/services/vision/service.py`: `VisionService.analyze()` (OpenRouter
  vision, tolerant JSON parse, 3 retries) as the **plate-OCR fallback (2)**
  before the ArUco fallback. Env: `OPENROUTER_API_KEY`,
  `OPENROUTER_VISION_MODEL` (default `inclusionai/ling-3.0-flash-vl:free`).
- `app/services/history.py`: `get_all_history/add_history_entry` if ticket
  prints should appear in history (route-level call only).
- `app/renderer/*`, `app/models/label_data.py`, `app/schemas/*`,
  `shared/config.py`, `infrastructure/database.py`: patterns/conventions only.
- `frontend/vite.config.js` `/api` proxy convention (new parking/robot API
  calls automatically proxied; no config change needed).

### LEAVE UNTOUCHED

- `app/services/printer.py`, `app/services/camera.py` internals (except one
  optional additive BGR accessor if vision needs it — prefer a wrapper first).
- `app/routers.py` existing routes and `HardwarePrintRequest` validation.
- `run_robot.py`, `app/hardware/simulator/*`, `app/state/state_machine.py`,
  `app/enums/*`, `app/renderer/*`, `backend/*`, `infrastructure/*`,
  `frontend/src/App.jsx` existing screens/flows, `requirements.txt`
  (robot deps go in additive requirements or env-gated imports),
  `.env.example` existing keys.
- `IMPLEMENTATION_SUMMARY.md`, `PrintSensei_Printer_Implementation_Handoff.md`,
  `README.md` (superseded only by new `docs/*` files; no edits).

### SMALL ADDITIVE EDITS allowed (each a few lines, reviewed in its phase)

- `app/main.py`: `+ app.include_router(robot_router)` /
  `app.include_router(parking_router)` (Phase 3 / Phase 5). Only edit.
- New routers live in new files (`app/api/robot_routes.py`,
  `app/api/parking_routes.py` following the existing `APIRouter()` pattern);
  `app/routers.py` itself is not edited.
- `frontend/src/App.jsx`: `+ import RoboticsPanel from './RoboticsPanel.jsx'`
  and one section render (Phase 3); no restructuring of existing screens.
- `.env.example`: **append** robot keys only
  (`SERIAL_PORT`, `SERIAL_BAUD`, `VEHICLE_DETECTOR`, `AUTOSTART`, …) (Phase 2+).
- `requirements.txt` or new `requirements-robot.txt`: add `pyserial`,
  `opencv-python-headless` (already present), `numpy`, `pydantic` (present),
  OCR lib choice (Phase 6) — additive lines only.

New code lives in new top-level modules per brief §3
(`backend/services/parking/`, `robot/`, `arduino/`, `tools/`, `deploy/`,
`tests/test_*_mock.py`, `docs/`). No new dependency may break laptop boot:
every hardware import stays behind try/except + mock fallback.

---

## 7. Hardware assumptions needing confirmation (questions for owner)

1. Printer: keep assuming **SHREYANS POSIFLOW 58D on USB 0456:0808**,
   ESC/POS 384-dot raster via `/dev/usb/lp0`, CUPS queue `POSIFLOW58D` fallback
   only — correct, and is the printer still on the Pi (not moved to laptop)?
2. Camera: keep assuming **Hikvision 1080P USB webcam (V4L2, 1280×720@30)**
   as the overhead camera for Phase 1 — or will the overhead view use a
   different USB camera / the Pi Camera Module v2 (which would need a new
   Picamera2 backend, not present today)?
3. Pi: brief says **Raspberry Pi 5** (with 5 V/5 A supply); README hardware
   table still lists **Pi 4B** — which board will run the demo, and what OS
   (Raspberry Pi OS 64-bit?) and Python version?
4. Arduino: **Uno + Adafruit Motor Shield V1 (L293D)** with `AFMotor.h`,
   motors on shield terminals only, external battery pack on shield power
   terminal with common ground — confirm shield version (V1 vs V2 changes the
   library/pins) and motor + battery specs (DC gear motors? voltage/capacity?).
5. Ultrasonic: **HC-SR04 with TRIG→A0, ECHO→A1 on the Arduino** (never Pi
   GPIO), 3–5 cm above table, stop threshold default 12 cm — confirm mount
   height and whether any level shifter/divider is already wired anywhere.
6. Free-pin map: brief reserves Arduino **4,7,8,12,11,3,5,6,9,10** for the
   shield; free are **A0–A5, 2, 13** — confirm nothing else is wired to the
   Uno today.
7. Serial: **USB serial 115200, line-based ASCII** (`PING/F/B/L/R/S/MOVE/DIST/
   STATUS/SET_STOP_CM`), Uno resets on connect (~2 s wait), port via
   `/dev/serial/by-id/*` fallback `/dev/ttyACM0`, Pi user in `dialout` + `lp`
   groups — confirm groups already set on the Pi?
8. Mat + markers: printed parking mat with **4 corner ArUco markers** for
   homography + **robot marker ID 10 (~4–5 cm)** on the chassis + plate cards
   in bold sans on each toy car — confirm mat physical size (cm), marker
   dictionary (e.g. `DICT_4X4_50`?), and how many toy cars/slots (brief
   example slot `A3`)?
9. Power: Pi powered by its own supply, Arduino logic over Pi USB, **motors
   never from Pi USB** — confirm separate motor battery pack is available and
   its wiring follows the shield power-jumper docs.
10. Network/demo host: FastAPI on port **8000** (`HOST`/`PORT` env), Vite dev
    on **5173** with `/api` proxy; dashboard polls 500–1000 ms — confirm the
    demo runs both on the Pi (systemd final) vs laptop dev, and whether
    `AUTOSTART=true` is desired on boot or IDLE-wait-for-START is preferred?
11. Secrets: no credentials in source/docs — confirm OpenRouter key (if plate
    fallback is wanted live) will be supplied **only via Pi `.env`** (never
    committed), and that `.env` stays gitignored (it does: `.env`, `.env.*`
    ignored, `!.env.example` kept)?

---

## 8. Phase scope acknowledgment

- Phase 0 gate: this file exists and owner has read it. **STOP here.**
- Phase 1 (next, after explicit confirmation only): `tools/test_camera.py` +
  reuse of `GET /api/camera/frame`; no Arduino/printer/driving work.
- Branch `robotics` to be created for all robot work; `main` stays clean;
  no push without instruction.

## 9. Quick file index (where to look next)

```text
app/main.py:33                        single-router mount + init_db startup
app/routers.py:369                    all current routes incl. /api/print + /api/camera/*
app/services/camera.py:128           CameraManager + singleton + status
app/services/printer.py:290          ESC/POS raster + transport + print_label()
tests/test_printer.py:79             ESC/POS header/size/packing/endpoint tests
run_robot.py:12 + simulator.py:219    desktop LCD simulator (pattern only)
shared/config.py:12                   env defaults (HARDWARE_MODE=pc)
.env.example:29                       printer + Azure/OpenRouter/NVIDIA keys
frontend/src/App.jsx:1008             LCD UI (CameraCapture/Camera+Voice flows)
frontend/vite.config.js:19            /api + /study + /voice proxies
requirements.txt:32                   fastapi/uvicorn/pydantic/SQLAlchemy/Pillow/pyusb/opencv-headless/pytest
```
