# ParkSensei — Complete Project Guide and Current-State Handoff

Purpose: give another developer or AI a useful, repository-based explanation of the product, software, UI, hardware, known status and roadmap. It describes checked-in code and project history known on 17 October 2026. Ask for fresh Pi output when current runtime state matters; hardware and deployment configuration can change.

Source-of-truth order: current source and Pi .env > focused current docs > this overview > older PrintSensei planning/chat notes.

## 1. What ParkSensei is

ParkSensei is a local-network smart parking-monitoring and supervised robot-patrol system. A Raspberry Pi 5 hosts a FastAPI backend, RapidOCR license plate recognition engine, and a React mobile-first HUD. A USB camera watches a tabletop parking mat. The **Dynamic Computer Vision Pipeline** automatically detects drawn black divider lines to synthesize $N$ parking bays on the fly, isolates multi-colored vehicle cards (yellow, red, black, etc.), and fits tight 4-point perspective quadrilaterals without Euclidean bounding box bloat.

The mobile HUD (`10.42.0.1:8000/hud`) shows live camera video, dynamic SVG polygon overlays, parking state, hardware status badges, touch manual drive controls, and ticket history. The operator can teleoperate manually via touch D-pad or start supervised auto patrol. When the robot detects a parking violation (e.g. straddling a bay line or angled parking), patrol halts automatically and an interactive **Verification Gate Modal** appears on the operator's screen. The operator can confirm/edit the OCR plate number, print a formal thermal citation via the onboard 58 mm printer, or dismiss false alarms before resuming patrol. An Arduino Uno plus Adafruit Motor Shield V1 drives the 4WD skid-steer chassis via safety-leased commands. Front IR and HC-SR04 ultrasonic obstacle sensors connect directly to Pi GPIO with non-blocking timeout protection.

Typical demo: camera dynamically detects marker bays and cards -> operator starts auto patrol -> Pi checks sensors and sends short forward leases to Arduino -> stop/attempt timed pivot at obstacles -> auto-halt and pop up verification gate upon parking violation -> operator verifies plate and prints thermal citation -> operator resumes patrol.

This is a supervised tabletop proof-of-concept. It is not public-road, production parking, enforcement, mapping, or safety-certified autonomous vehicle software. Do not claim it navigates real parking lots independently.

## 2. Repository map and legacy scope

| Path | Responsibility |
| --- | --- |
| app/main.py | FastAPI setup, router registration, CORS, generated-file mounts, optional frontend/dist serving. |
| app/api/robot_routes.py | Robot states, non-blocking Pi GPIO sensors, manual/auto, E-stop and review gate. |
| app/api/parking_routes.py | Parking APIs, monitor start/stop, annotated frame and MJPEG stream. |
| app/api/hud_routes.py | Composite HUD data, device status, test-print/history/violation ticket. |
| app/api/deps.py | Optional Bearer API key check. |
| app/hardware/arduino_serial.py | Uno serial discovery, handshake and command transport. |
| arduino/park_sensei_serial/park_sensei_serial.ino | Uno + Motor Shield V1 firmware. |
| app/services/camera.py | OpenCV camera manager and cached frames. |
| backend/services/parking/dynamic_detector.py | Dynamic marker line & bay detector, tight perspective quads, relative violations. |
| backend/services/parking/monitor.py | Dynamic CV monitor loop with classical fallback. |
| backend/services/parking/vehicle_detector.py | Classical red/dark paper-car segmentation fallback. |
| backend/services/parking/parking_geometry.py | Polygon overlap, angle rules and debounce. |
| backend/services/parking/analyzer.py | Combines detections and parking slots. |
| backend/services/parking/plate_reader.py | RapidOCR ONNX plate recognition on rectified vehicle crops. |
| backend/services/parking/config/slots.json | Tabletop metric calibration & fallback slot definitions. |
| backend/services/parking/ticket.py | Ticket image layout, barcode, PNG and JSON history. |
| app/services/printer.py | 58 mm raster and USB/CUPS/Bluetooth ESC/POS output. |
| frontend/src/App.jsx | ParkSensei home and ticket history. |
| frontend/src/hud/HudPage.jsx | Main mobile-first robot/parking HUD. |
| frontend/src/hud/components/ReviewModal.jsx | Operator verification gate modal for violation approval & plate edit. |
| frontend/src/hud/components/ManualDriveSheet.jsx | Touch D-pad manual teleoperation drawer. |
| frontend/src/hud/components/ControlsBar.jsx | Floating tactical bottom dock with auto/stop/estop controls. |
| frontend/src/hud/api.js | HUD HTTP client with safe 20s auto timeout and descriptive abort handling. |
| deploy/ARDUINO_SERIAL.md | Wiring, Uno commands and test notes. |
| context.md | Hardware/network history, updater documentation, and current status. |

Repo originated as PrintSensei, an AI label/diagram/voice/printing assistant. Old renderer, AI providers, speech, simulator, display/LCD, legacy endpoints and RoboticsPanel.jsx remain. Active React routes are /, /hud and /history. Do not remove legacy modules without reference/dependency review. Branding is partly migrated: home/history say ParkSensei, while HUD header/title, APP_NAME default, startup log and service filename still say PrintSensei.

## 3. Architecture

Browser does not access GPIO or serial directly. It calls Pi via HTTP(S). Pi owns camera, vision analysis, GPIO reads, serial and printing. Arduino receives drive commands and owns motor lease timing. Printer connects to Pi, not Arduino.

    Browser: ParkSensei React UI
      | HTTP(S): JSON, MJPEG, PNG
    Raspberry Pi 5: FastAPI + OpenCV + GPIO Zero
      | camera USB / GPIO sensors / USB serial / thermal printer
    Arduino Uno -> Adafruit Motor Shield V1 -> four DC motors

## 4. Hardware and connections

### Raspberry Pi 5
Runs Linux, FastAPI and GPIO Zero/lgpio. Observed deployment: user ps, repo /home/ps/Robotics_new, venv /home/ps/Robotics_new/venv, systemd service printsensei-robot, Uvicorn on 0.0.0.0:8000. Checked-in unit template may use old /home/pi path; deployed systemd config is the authority.

### Arduino and motor shield
- Uno USB serial at 115200 baud, ASCII newline protocol.
- Adafruit Motor Shield V1 using AFMotor.h (not V2/I2C).
- M1+M3 are left-front/rear; M2+M4 right-front/rear.
- External motor supply powers shield/motors. Never use Pi/Uno USB as motor supply.
- Firmware forces every nonzero requested speed to PWM255 because loaded motors only reliably started there in user test. UI slider currently does not represent physical speed.
- MOVE duration clamped 100–500 ms; expiration releases outputs. Opening USB serial resets Uno; backend waits ~2s and requires PING/PONG.
- L/R counter-rotate both sides. Motor polarity may invert physical forward; test with wheels raised.

Commands:
    PING -> PONG
    MOVE F|B|L|R <pwm> <ms> -> OK MOVE
    STOP -> OK STOP
    ESTOP -> OK ESTOP (latched until CLEAR)
    CLEAR -> OK CLEAR
    STATUS -> STATUS IDLE|MOVING|ESTOP

Pi .env: ROBOT_MODE=real, ROBOT_SERIAL_PORT=/dev/serial/by-id/<exact-device>, ROBOT_SERIAL_BAUD=115200. Otherwise code searches /dev/serial/by-id/*, /dev/ttyACM0, /dev/ttyUSB0. Install pyserial and grant service user serial access (usually dialout). See deploy/ARDUINO_SERIAL.md.

Shield is a driver, not motor energy source. Start with wheels raised, then a clear supervised area and physical cutoff within reach. Software E-stop depends on backend/serial; lease expiry is a fallback, not a hardware E-stop.

### HC-SR04 on Pi
- VCC to 5V physical pin 2; GND to physical pin 14.
- TRIG to BCM GPIO5 physical pin 29.
- ECHO to BCM GPIO6 physical pin 31 through divider: 1 kΩ from ECHO to GPIO6 junction, 2 kΩ from junction to GND.
- Do NOT connect 5V ECHO directly to Pi GPIO. Share ground.
Old experiments wired sonar to Uno A0/A1; current Uno sketch has no sonar logic and current project reads Pi GPIO5/6.

Code lazily creates gpiozero.DistanceSensor(echo=6, trigger=5, max_distance=4.0, queue_len=1). Pins override via ROBOT_ULTRASONIC_TRIGGER_GPIO and ROBOT_ULTRASONIC_ECHO_GPIO. Reading is metres from GPIO Zero multiplied to centimetres; HUD rounds to whole cm. Obstacle threshold ROBOT_OBSTACLE_CM defaults 18. Positive reading <= threshold means close. Zero/no echo currently becomes unknown/clear rather than fault, a known fail-open issue. A single forward sonar cannot select a safe turn.

User said standalone readings changed accurately with objects (e.g. ~5.7, 15–42, 96–137 cm). GPIO5/6 chosen after GPIO23/24 contention.

### HW-201 digital IR on Pi
- VCC to Pi 3.3V physical pin 1 (keeps OUT Pi-safe).
- GND to physical pin 6.
- OUT to BCM GPIO22 physical pin 15.
It is a short-range reflective binary switch, not a range sensor. Potentiometer sets detection threshold. Range depends on target color/material, angle and light. User saw red indicator and verified GPIO22 toggled clear/detected with card. Code uses gpiozero.DigitalInputDevice(gpio, pull_up=False) and raw value==0 means blocked (active-low). Earlier explicit active_state=False caused PinInvalidState; current code omits active_state.

Override with ROBOT_IR_GPIO. Earlier gpioinfo showed GPIO24 output consumer dc; stopping service did not immediately release. Check fresh gpioinfo for pin ownership.

### How sensors combine
_sensor_reading reads ultrasonic then IR. Obstacle is logical OR:
    ir_blocked OR (distance_cm > 0 AND distance_cm <= ROBOT_OBSTACLE_CM)
Either sensor can stop the robot. IR gives close binary proximity; sonar estimates forward range. Both are Pi-connected. HUD displays each separately and combined path state. Device status marks a sensor seen after successful read, not after an electrical/range self-test.

Auto preflight fails on read/construction exceptions, but no-echo is not an exception. Patrol stops immediately on first positive obstacle reading and requires a second positive sample before pivot. Wrong orientation, broken wire, reflectance, no echo, or missed threshold may appear clear. Add health/timeout fault detection before relying on auto in anything beyond demo.

## 5. Camera and calibration

USB camera is mounted to view the tabletop mat. Prior docs call it a Hikvision USB camera, but exact current Pi model/index must be checked live. Auto requires both live frame and fresh parking analyses.

app/services/camera.py:
- Uses OpenCV. Linux tries V4L2 then default, tries 1280x720 @30, probes for non-black frames and falls back to native mode if forced HD is black.
- Linux selects first existing /dev/video0..2; CAMERA_INDEX overrides. Windows probes indices.
- Caches JPEG quality 80, raw frame, ID, dimensions and brightness; releases after >3 sec inactivity; reopens dead/black stream.
- HUD Retry restarts feed. Pi logs historically contained “Could not open USB camera”; current availability unknown.
- Fixed camera/mat geometry is essential; moving either invalidates calibration.

Current slots.json says mat 60x45 cm, image_size 1920x1080, homography and bays A1/A2/A3. Older notes discuss 1280x720 and 640x480 experiments. Current file plus actual frame dimensions are authority. Revalidate overlay across full mat after every camera/mat movement.

## 6. Vision and ticket logic

### Detector and parking rules
Detector is classical OpenCV, not trained ML. It segments saturated red and near-black HSV pixels; morphology closes 9x9 gaps, opens 5x5 noise, limits to calibrated ROI, filters contour area/long side, creates minimum-area rectangle, maps contour into mat cm with perspective homography, finds long-axis angle. Sorts detections left-right and assigns temporary CAR-01 etc. Confidence is fixed 0.9 heuristic, not calibrated model probability. Targeted at colored paper/toy cars on contrasting tabletop, not arbitrary cars.

For each vehicle, overlap is intersection area / vehicle area. Rules/thresholds from parking_geometry.py, in order:
1. NO_PARKING_ZONE: >=10% overlap with restricted zone.
2. STRADDLING: >=15% overlap with two non-restricted slots.
3. OUTSIDE_SLOT: best open slot overlap <80% or none.
4. WRONG_ORIENTATION: >=80% inside slot, but heading error >25°.
5. LEGAL otherwise.
Angle folds modulo 180 because slot is an axis. Result includes slot, violation enum, confidence, overlap fraction and angle error. Debouncer requires at least 5 violating observations in last 8; monitor defaults ~1Hz. Event logs on transition to violation.

No detections is represented no vehicle and default parking-valid. Missing calibration falls back to NullDetector; can look like no cars rather than fatal error. Verify camera, calibration and overlays before trusting classification.

### Calibration and OCR
slots.json defines pixel-to-centimetre homography, mat corners, image size and slot polygons. Current slots A1/A2/A3 open. Recalibrate after moving camera/mat using tools/calibrate_table.py and check against live feed.

RapidOCR is loaded on first car detection, crops calibrated vehicle and tests rotated crop. Failure leaves plate absent, not guessed. UI asks operator to verify/correct. IDs are temporary and may swap as cars move. plates.json is fictional demo mapping, not personal data registry.

### Monitor
app/startup.py initializes DB and starts parking monitor on backend boot. This differs from older docs saying it starts on HUD request. Monitor independent of robot motion; each tick obtains camera, detects, optionally OCRs, analyzes, debounces and stores latest in process memory. Camera errors are caught/logged and thread continues. API still supports idempotent monitor start/stop.

### Receipt and printer
ticket.py renders 384px width for 58mm thermal printer, numbers tickets, writes generated_labels PNG and JSON history app/database/parking_tickets.json. Printer service converts to monochrome ESC/POS and supports PyUSB, /dev/usb/lp0, CUPS or Bluetooth RFCOMM. Current source references SHREYANS POSIFLOW 58D. Old notes found Bluetooth SPP channel 2 but did not record confirmed successful physical print; verify current Pi .env/device and test.

Local ticket.py was redesigned recently: heading, boxed plate, aligned fields, highlighted violation, disclaimer, text wrapping. Last observed git status showed ticket.py modified/uncommitted. Physical print not verified; do not claim live on Pi until pushed/pulled/tested. Ticket is a demo notice, not real fine; do not add legal enforcement claims or invented amounts.

## 7. Robot states and modes

Internal mode idle/auto/review/blocked plus E-stop latch. UI states IDLE, MONITORING, PATROLLING, PAUSED_REVIEW, BLOCKED, ESTOP.

Mock mode (ROBOT_MODE=mock default example) acknowledges drive commands without physical motion. Real mode activates serial. Real auto start requires online Arduino, live camera, successful GPIO sensor reads and confirmed idle STOP. Start runs monitor and real-mode daemon patrol thread.

Auto loop:
1. Wait for new fresh analysis. Camera loss or no new analysis within startup timeout (default20s, min5) blocks; >5s stale analysis during run stops/blocks.
2. Check new persistent violation first. Confirm STOP, enter review, store vehicle IDs and clear confirmation/ticket state.
3. When vision ready, read sensors. On obstacle send STOP immediately. Require second consecutive obstacle sample before turn.
4. Perform timed pivot alternating L/R. Defaults PWM255, lease220ms, turn350ms; firmware clamps MOVE lease 100–500ms. STOP after turn and recheck.
5. Four failed pivots -> blocked.
6. When path clear, send short MOVE F and reevaluate ~60ms later.
7. Stop event cancels loop and sends STOP. E-stop sends latched ESTOP, Clear sends CLEAR.

No encoders, IMU, localization, path planning, side/rear sensing, measured heading, closed-loop speed. Alternating pivots are only attempts and cannot ensure clear direction.

Review gate: operator confirms each flagged vehicle, provides/verifies plate (4–16 chars after sanitation), successfully prints for each, then Go ahead becomes available. Backend only marks ticketed on printer success. Resume suppresses reviewed IDs until debouncer clears, resets review state and starts new loop.

Manual API accepts F/B/L/R/S. Browser hold refreshes command every 200 ms with 200ms lease; attempts STOP on release/leave, window blur, hidden tab, sheet close and Stop. Arrow/WASD while sheet open. Slider 50–200 step5, default120, but firmware raises nonzero to255. API rejects manual during auto/review/E-stop/offline.

E-stop sticky-bar button and Space shortcut (unless editing text). Banner offers Clear/reset. Software E-stop still depends on backend/serial; retain physical power disconnect.

## 8. UI feature inventory

### Home /
ParkSensei logo, Parking monitor label, Open live HUD card, Ticket history card and local self-hosted note.

### Live HUD /hud
- Responsive camera/main panel and side cards; dark theme default, light/dark toggle in localStorage.
- Polls /api/hud/state every ~1.5 sec while visible, pauses hidden and refreshes on return; shows backend-offline banner.
- Badges Camera, Arduino, Ultrasonic, IR, Printer, Backend. Status Ok/Degraded/Offline/Simulated with tooltips; printer OK is heuristic, not print proof.
- MJPEG stream primary; fallback to frame polling every250ms after stream error; Retry button. Overlay data older than1 sec fades and “Overlay delayed” appears.
- Layer switches: parking slots, vehicles, plates. Slots white; legal vehicles green, violations red; labels include ID/slot/state and OCR plate.
- Robot state card with state/help, ultrasonic cm, IR blocked/clear, combined path, blocked error and step chips Check parking -> Patrol -> Avoid obstacle -> Confirm -> Print -> Continue.
- Violations card: counts, empty/all-legal/updating states; per car ID, violation, slot, confidence, OCR confidence, editable plate, Confirm bad parking, Print ticket, review progress, Go ahead.
- Ticket card preview, number/status, reprint, PNG download, printer-failure note.
- Sticky Start auto, Stop, Manual drive, Print test, E-stop. Initial auto safety dialog; controls disabled by state/link/E-stop.
- Manual slide sheet: direction pad, arrows/WASD, speed slider, release-to-stop.
- E-stop banner, toast confirmations/errors, latest100 in-memory event log with severity/time.

### Ticket history /history
Newest-first number/status, plate, vehicle ID, bay, violation, local date/time and View ticket. Refresh, loading/error/retry, empty states.

Freshness semantics: API polling, stream and overlays have distinct timing. Overlay delayed refers to HUD data age; validate that geometry sits on live mat. Printer badge does not prove paper was emitted. Sensor “OK” means read at least once, not validated range.

Branding: home/history are ParkSensei; HUD title is still “PrintSensei robot”, document title likewise.

## 9. API inventory

Robot/parking/HUD routers use optional Bearer auth. API_KEY empty means auth helper allows requests; nonempty requires Authorization: Bearer <key>. CORS currently broad; harden before public exposure.

HUD/ticket:
- GET /api/hud/state composite.
- POST /api/ticket/test-print.
- GET /api/ticket/history.
- POST /api/ticket/violation.

Parking:
- POST /api/parking/analyze synthetic/current detections in cm.
- GET /api/parking/status.
- POST /api/parking/monitor/start and /stop.
- GET /api/parking/frame JPEG.
- GET /api/parking/stream MJPEG.

Robot:
- GET /api/robot/status.
- POST /api/robot/command.
- POST /api/robot/estop and /api/robot/estop/clear.
- POST /api/robot/auto/start, /stop, /resume.
- POST /api/robot/review/confirm.

Legacy app/routers.py still exposes health/system status, old camera APIs, /api/print, /api/history, voice, /simulate, /render, /study/generate and root fallback. Retained PrintSensei APIs, not main ParkSensei React flow.

## 10. Configuration, deployment and access

Related root .env.example keys:
    ROBOT_MODE=mock
    ROBOT_SERIAL_PORT=/dev/serial/by-id/<device>
    ROBOT_SERIAL_BAUD=115200
    ROBOT_AUTO_PWM=255
    ROBOT_AUTO_LEASE_MS=220
    ROBOT_AUTO_TURN_MS=350
    ROBOT_OBSTACLE_CM=18
    ROBOT_IR_GPIO=22
    ROBOT_ULTRASONIC_TRIGGER_GPIO=5
    ROBOT_ULTRASONIC_ECHO_GPIO=6
    API_KEY=
    CAMERA_INDEX=
    PRINTER_TRANSPORT=usb
    PRINTER_DEVICE=/dev/usb/lp0
    CUPS_QUEUE=POSIFLOW58D
    PRINTER_USE_CUPS=false
    PRINTER_BLUETOOTH_ADDRESS=
    PRINTER_BLUETOOTH_CHANNEL=1

Code clamps lease/turn duration to 100–500ms and PWM1–255. ROBOT_VISION_STARTUP_TIMEOUT_S default20s/min5; stale-analysis stop after5s. Keep .env private, gitignored, and do not paste full file in chat.

Observed Pi venv is /home/ps/Robotics_new/venv. User initially failed pip lgpio source build because swig absent, then successfully installed gpiozero 2.0.1.post3 and lgpio 0.2.2.0 and reported import success. Whether service restarted after install is unknown. Build prerequisites were python3-dev swig liblgpio-dev.

Pi commands:
    sudo systemctl status printsensei-robot --no-pager
    sudo systemctl restart printsensei-robot
    sudo journalctl -u printsensei-robot -n 80 --no-pager
    systemctl cat printsensei-robot

Frontend: cd frontend; npm ci; npm run dev. Vite proxies backend at 127.0.0.1:8000. Empty VITE_API_URL means same-origin/proxy; hosted frontend sets VITE_API_URL to Pi/tunnel and optional VITE_API_KEY. VITE_* values are client-visible after build; never put private provider credentials there. FastAPI serves frontend/dist if present.

Network: Pi NetworkManager profile printsensei-hotspot, SSID PrintSensei, historically 10.42.0.1/24. On: sudo nmcli connection up printsensei-hotspot. Off: sudo nmcli connection down printsensei-hotspot. Either can terminate SSH if that is the current connection; ensure another access path first. Saved profile remains. Hotspot gives local access, not automatic internet. Earlier Windows ICS failed; phone profile Pranshu eventually gave Pi internet and git pull succeeded. No Wi-Fi secrets are in this doc. See context.md for details.

## 11. Confirmed reports vs unknown

User-reported physical checks:
- All four loaded motors started at PWM255 on V1 shield.
- HW-201 LED and GPIO22 card detection worked.
- HC-SR04 on Pi5 GPIO5/6 produced target-dependent readings the user said were accurate.
- Pi internet/GitHub pull worked via Pranshu; user wanted hotspot back.
- GPIO Zero/lgpio install/import succeeded in Pi project venv.

Historical service was active but logs showed OpenCV “Could not open USB camera”. Current camera state unknown. Ticket renderer redesign is uncommitted in local status and not physically print-tested. Current service restart following GPIO package install is unknown. Camera model/index, live overlay/calibration, printer transport/paper output, motor direction and current auto reliability require fresh verification.

Old docs may conflict (sonar-on-Arduino experiment; earlier statement motors deferred). Current code has both sensors on Pi and active Arduino control. Source wins.

## 12. Limitations and risks

- Red/dark paper-car detector, not general real-car recognition; lighting/occlusion can break it.
- IDs are temporary left-to-right, not persistent tracking.
- Calibration tied to camera/mat pose.
- OCR optional and fallible; human should verify.
- No localization, encoders, IMU, path planning, closed-loop speed/heading.
- One front sonar + short-range IR cannot see behind/sides or determine safe turning path.
- No sonar echo currently treated unknown/clear: possible false negative.
- IR depends on reflectance, angle, light, potentiometer threshold.
- Slider 50–200 but physical command always 255 currently.
- Software E-stop depends on Pi/serial.
- Multiple Uvicorn workers may duplicate camera/GPIO/control threads; normally keep a single worker.
- Events and robot/review state in memory reset on restart; tickets persist as local JSON.
- Printer badge checks config/device heuristic, not confirmed output.
- API key optional, CORS broad, frontend key public. Do not expose publicly without hardening.

## 13. Future scope (not currently implemented)

P0 reliable demo: verify service config/single worker/venv/serial; restore camera and validate live overlay; detect sonar no-echo as sensor fault/fail closed; calibrate stopping threshold against measured braking distance, IR on varied targets; test motor direction, E-stop, lease timeout and sensor stop with wheels raised; resolve PWM slider mismatch; physically test printer and truthful status; clean-Pi deployment/rollback.

P1 perception: recalibrate mat, stable tracking IDs, test on captured mat data, improve lighting/color/overlap robustness, show explicit camera/calibration/stale/no-car states, validate thresholds, expose configurable slot/rule UI, keep OCR uncertainty visible.

P2 robot autonomy: add encoders/IMU, closed-loop speed/heading and measured turn; side/rear sensing; localization, mapped safe area, route planning, boundary and recovery logic; watchdog/hardware E-stop; simulation/replay before increasing autonomy. Keep human approval and do not imply enforcement authority.

P3 product/ops: finish branding migration; persistent events/review and retention/export policy; health diagnostics with last sensor read, serial handshake, camera and print-confirmed state; UI calibration/safe controls; API auth/CORS/TLS/least privilege; offline install/update/backup.

## 14. Guidance for the next AI

1. Read this, context.md, deploy/ARDUINO_SERIAL.md, then current source.
2. Ask for fresh logs when current Pi state matters; do not assume old IP, route, pin owner, service path or camera/printer status.
3. Preserve short motor leases, stop-on-error, E-stop and review confirmation/print gate.
4. State whether a claim is code capability, user-reported test, or live verification.
5. Do not request/record secrets; use targeted redacted .env checks.
6. Lift wheels first for motor changes; supervise and keep physical cutoff available.
7. No external messaging or remote changes without user authorization/capability.
8. Public name is ParkSensei; legacy symbols remain until separately scoped migration.

## 15. Handy commands and reading

Pi diagnostics:
    sudo systemctl status printsensei-robot --no-pager
    sudo journalctl -u printsensei-robot -n 80 --no-pager
    systemctl cat printsensei-robot
    ls -l /dev/serial/by-id/
    ls -l /dev/video*
    sudo gpioinfo | grep -E 'GPIO5|GPIO6|GPIO22'
    cd ~/Robotics_new
    ./venv/bin/python -c "import gpiozero, lgpio, serial, cv2; print('robot imports OK')"

Local development:
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    cd frontend
    npm ci
    npm run dev

Further docs: README.md quick start; context.md hardware/network and hotspot commands; deploy/ARDUINO_SERIAL.md; docs/DEPLOY.md (historical paths may be stale); docs/REMOTE_ARCHITECTURE.md (predates integrated drive in parts); docs/CAMERA_HUD_HANDOFF.md and docs/CAMERA_NOT_FOUND_DIAGNOSIS.md; PrintSensei_Printer_Implementation_Handoff.md (historical, verify current setup).
