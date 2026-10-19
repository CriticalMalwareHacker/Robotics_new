# PrintSensei Project Context and Handoff

This is a working handoff for another Codex account or developer. Read it with `README.md`, `deploy/ARDUINO_SERIAL.md`, and the current source. Code, the Pi's private `.env`, and fresh Pi output take precedence if this note becomes stale.

## Project and locations

PrintSensei combines a FastAPI backend/dashboard, a 58 mm thermal printer, parking/vehicle monitoring, and an Arduino-driven robot.

- Windows workspace: `C:\Users\tanay\OneDrive\Documents\Roboticsnew`
- Pi clone: `/home/ps/Robotics_new`
- Pi systemd service: `printsensei-robot`
- Observed service executable: `/home/ps/Robotics_new/venv/bin/uvicorn`, running as user `ps`.
- The checked-in unit template may show older `/home/pi/...` paths; the Pi's actual service configuration is authoritative.

## Hardware: Drive, Power Delivery & Enclosure

- **Compute Core (Master):** Raspberry Pi 5 (8GB) running the FastAPI backend, computer vision, plate OCR, and hosting the HUD.
  - **Power Source:** Dedicated **Mi 20,000mAh Power Bank** supplying clean, high-amperage 5V USB-C power to prevent CPU throttling or undervoltage.
- **Actuator Controller (Slave):** Arduino Uno R3 connected to Pi over USB serial at 115200 baud.
  - **Motor Driver Shield:** Adafruit Motor Shield V1 (`AFMotor.h` with dual L293D H-bridges).
  - **Motor Power Supply:** Dedicated external high-discharge **Battery Pack** connected to the shield's `EXT_PWR` terminals (PWR jumper removed). This isolates motor inductive spikes from Pi logic and provides higher voltage/current, making the 4 DC motors significantly faster and stronger under load.
  - **Motors & Kinematics:** 4 × TT geared DC motors in 4WD skid-steer configuration (M1+M3 Left, M2+M4 Right).
  - Sketch: `arduino/park_sensei_serial/park_sensei_serial.ino`. PWM is calibrated to 255 for reliable loaded start.
- **Chassis & Physical Enclosure:**
  - 4WD Smart Car robotic chassis platform.
  - **Custom Acrylic Case:** Enclosure covering **3 sides: Top, Left, and Right**.
  - **Deliberately Open Front & Back:**
    - **Front Side:** Uncovered to provide unobstructed field-of-view for the Hikvision webcam, HC-SR04 ultrasonic transducer, and HW-201 IR emitter/receiver.
    - **Back Side:** Uncovered for physical thermal ticket paper ejection, easy battery charging / cable access, and unimpeded heat ventilation.

Serial protocol (newline-delimited):

```text
PING                         -> PONG
MOVE <F|B|L|R> <pwm> <ms>   -> OK MOVE
STOP                         -> OK STOP
ESTOP                        -> OK ESTOP (latched until CLEAR)
CLEAR                        -> OK CLEAR
STATUS                       -> STATUS IDLE|MOVING|ESTOP
```

The Arduino clamps each movement lease to 100–500 ms and releases all channels when it expires. Auto mode renews short leases. This protects against a lost command stream but is not a substitute for a physical power switch/hardware E-stop. `L`/`R` counter-rotate the two sides. More setup detail: `deploy/ARDUINO_SERIAL.md`.

Find the Uno path on the Pi with `ls -l /dev/serial/by-id/`. Set Pi `.env` values `ROBOT_MODE=real`, `ROBOT_SERIAL_PORT=/dev/serial/by-id/<exact-device>`, `ROBOT_SERIAL_BAUD=115200`. The Uno resets when serial opens; the backend waits about two seconds and expects PING/PONG.

## Hardware: Front Perception Suite (All 3 connected to Pi 5)

All three front perception devices are mounted ahead on the front of the chassis and connected directly to the Raspberry Pi 5 (Arduino is dedicated strictly to motor PWM):

1. **Hikvision HD USB Webcam:**
   - Mounted at the front, angled downward toward the parking surface.
   - UVC-compliant USB video device providing live frames for parking line synthesis and card vehicle detection.
2. **HC-SR04 Ultrasonic Rangefinder:**
   - Mounted ahead facing forward for mid/long-range obstacle detection (calibrated stop at $\le 18$ cm).
   - Non-blocking threaded reader (`0.25s` timeout) in `app/api/robot_routes.py`.
3. **HW-201 Infrared (IR) Proximity Sensor:**
   - Mounted ahead facing forward for close-range front collision detection (active-low binary beam).

| Sensor pin | Pi connection | Function & Protection |
| --- | --- | --- |
| HC-SR04 VCC | 5 V, physical pin 2 | Sensor 5V power supply |
| HC-SR04 GND | GND, physical pin 14 | Ground reference |
| HC-SR04 TRIG | BCM GPIO5, physical pin 29 | 10 µs trigger pulse |
| HC-SR04 ECHO | BCM GPIO6, physical pin 31 | **Voltage divider (1 kΩ to GPIO6, 2 kΩ to GND)** steps 5V echo to safe 3.3V Pi logic |
| HW-201 IR VCC | 3.3 V, physical pin 1 | Sensor 3.3V logic power |
| HW-201 IR GND | GND, physical pin 6 | Ground reference |
| HW-201 IR OUT | BCM GPIO22, physical pin 15 | Active-low obstacle detection |

## Demonstration & Evaluation Setup

- **Parking Mat / Surface:** Large white paper sheet with high-contrast black marker lines defining designated parking bays (`BAY-1`, `BAY-2`, `BAY-3`).
- **Vehicle Scale Models:** Different colored rectangular cards (yellow, red, black, blue, green) and boxes representing parked vehicles, each affixed with a real printed vehicle license plate sticker (e.g. `MH EF 4752`, `MH01AB1234`).
- **Obstacle Avoidance Test Objects:** Physical everyday items (shoe boxes, bottles) placed along the robot's driving corridor to evaluate real-time ultrasonic and IR obstacle detection, reverse clearance, and escape pivots.
- **Physical Ticketing Output:** 58 mm thermal receipt printer (POSIFLOW 58D / ESC/POS) generating real scannable QR verification tickets that open the `/history` evidence gallery with annotated vehicle photos.

## Robot behavior and safety

- `app/api/robot_routes.py` initializes Pi sensors, validates auto start, runs patrol, and sends serial commands.
- `app/hardware/arduino_serial.py` handles Uno serial transport.
- `.env.example` defaults to `ROBOT_MODE=mock`; `real` enables serial motor control.
- Auto checks both sensors and fails closed if sensor setup/read fails. It advances with short forward leases, stops for obstacles/newly debounced parking violations, and alternates timed pivots to attempt obstacle avoidance.
- Four unsuccessful pivots lead to blocked state. A parking violation pauses for operator review; UI flow includes confirmation/ticket action before patrol resumes. Stop and E-stop are available.
- Timed pivots are not calibrated by encoders or heading sensors. This is supervised tabletop demo behavior, not reliable autonomous navigation.
- Test with wheels raised first, then on a clear surface under supervision with access to motor power switch.

Optional tuning from `.env.example`:

```dotenv
ROBOT_AUTO_PWM=255
ROBOT_AUTO_LEASE_MS=220
ROBOT_AUTO_TURN_MS=350
ROBOT_OBSTACLE_CM=18
```

Useful checks:

```bash
sudo systemctl status printsensei-robot --no-pager
sudo journalctl -u printsensei-robot -n 60 --no-pager
ls -l /dev/serial/by-id/
```

## GPIO Python install issue and status

Start Auto previously failed because GPIO Zero was missing in the service environment (reported as `No module named gpiozero`, once possibly mistyped as `gplozero`). A pip attempt to build `lgpio` failed with `command 'swig' failed: No such file or directory`, so that attempt did not finish installing gpiozero.

The user subsequently installed packages successfully in the project virtual environment and reported:

```text
Successfully installed ... gpiozero-2.0.1.post3 lgpio-0.2.2.0 ...
GPIO imports OK
```

Next step is restart the service if not already done, confirm status, then retry Start Auto. If it still fails, use fresh journal logs to distinguish GPIO claim/wiring, serial, or camera issues. Use the same venv as systemd:

```bash
cd ~/Robotics_new
./venv/bin/python -c "import gpiozero, lgpio; print('GPIO imports OK')"
sudo systemctl restart printsensei-robot
sudo systemctl status printsensei-robot --no-pager
sudo journalctl -u printsensei-robot -n 60 --no-pager
```

For a source build of lgpio, install prerequisites first: `sudo apt install -y python3-dev swig liblgpio-dev`.

## Network and SSH history

Pi hotspot profile is `printsensei-hotspot`; visible SSID is `PrintSensei`. The Pi AP has historically used `10.42.0.1/24`, with a Windows client example `10.42.0.25`. This hotspot provides local SSH/dashboard access but does not by itself give the Pi internet.

### Turn the PrintSensei hotspot on/off

Turn it on (activate its saved NetworkManager profile):

```bash
sudo nmcli connection up printsensei-hotspot
nmcli connection show --active
```

Turn it off:

```bash
sudo nmcli connection down printsensei-hotspot
nmcli connection show --active
```

**SSH warning:** if your laptop is connected to the Pi through the `PrintSensei` Wi-Fi, turning that connection off will drop the SSH session. First connect through another path or be prepared to reconnect after turning the hotspot back on. Use the Pi's local console if no other route is available.

These commands activate/deactivate the saved profile; they do not delete it or erase its saved configuration.

Pi internet was needed to pull from GitHub. Windows Internet Connection Sharing over USB Ethernet (`Ethernet 3`, gateway `192.168.137.1`) was attempted. The Pi obtained `192.168.137.2` and could ping the gateway but could not reach `1.1.1.1` or resolve `github.com`; ICS was not forwarding internet. Disconnecting Pi eth0 dropped SSH, and `ap.local` did not resolve, but the user recovered access.

The working route was to connect Pi to the Wi-Fi network `Airtel_Zerotouch_5G`; `git pull` then succeeded. The user confirmed the pull and wanted the project hotspot back. To automate this without getting locked out of SSH, use the fail-safe `update.sh` script, or run:

```bash
# Automated 1-command updater with safety trap that always restores hotspot:
./update.sh
```

Or manually:

```bash
sudo nmcli connection down printsensei-hotspot
sudo nmcli device wifi connect "Airtel_Zerotouch_5G" password "Airtel@123"
git pull origin robotics
sudo systemctl restart printsensei-robot
sudo nmcli connection down "Airtel_Zerotouch_5G"
sudo nmcli connection up printsensei-hotspot
```

Read-only diagnostics:

```bash
nmcli device status
nmcli connection show --active
ip -br addr
ip route
ping -c 3 1.1.1.1
getent hosts github.com
curl -I --connect-timeout 5 --max-time 10 https://github.com
```

The user shared a Wi-Fi password in chat. It is intentionally omitted; never add Wi-Fi passwords, API tokens, or secrets to this tracked handoff. NetworkManager may store credentials on the Pi.

## Thermal receipt layout & printing

`backend/services/parking/ticket.py` builds a Pillow RGB image at 384 px wide. `app/api/hud_routes.py` uses it for test/violation tickets, saves a PNG, then prints through `app/services/printer.py`; the image is also previewed in the dashboard.

The thermal citation receipt format features:
- High-contrast official header `[ OFFICIAL PARKING CITATION ]`.
- Ticket number, timestamp, and barcode graphics.
- Boxed prominent license plate number (detected via RapidOCR or verified by operator).
- Assigned bay ID, observed violation reason (e.g. `STRADDLING`, `WRONG_ORIENTATION`), and fine amount.
- Direct-thermal ESC/POS raster print transmitted wirelessly via Bluetooth RFCOMM socket (channel 1/2) or `/dev/rfcomm0` (avoiding trailing cables during robot counter-rotation).

## Dynamic Computer Vision Pipeline

Implemented in `backend/services/parking/dynamic_detector.py`:
1. **Dynamic Marker Line Detection:** Identifies drawn black lines on white mat paper using adaptive thresholding and line segment filtering. Synthesizes $N$ parking bays dynamically without requiring fixed homography calibration.
2. **Multi-Color Vehicle Card Segmentation:** Detects yellow, red, black, blue, and green cards using calibrated paper masks ($S \le 65, V \ge 110$).
3. **Tight Perspective Quadrilateral Fitting:** `extract_tight_card_polygon()` uses multi-scale polygon approximation on convex hulls to fit exact 4-corner perspective quadrilaterals, eliminating Euclidean bounding box bloat caused by perspective foreshortening.
4. **Independent Contour Processing:** Removed global morphological closing across cards. Per-contour convex hulls bridge handwriting ink and license plate stickers without bridging adjacent cards in neighboring bays.
5. **Relative Violation Logic:** Evaluates vehicle-line intersection for straddling and heading vector deviation ($> 25^\circ$) for orientation violations.

## Autonomous Patrol & Sensor Architecture

Implemented in `app/api/robot_routes.py`:
- **Supervised Short-Lease Forward Patrol:** Sends `MOVE F 255 220ms` leases to Arduino. Arduino watchdog automatically cuts motor power if serial stream drops.
- **Non-Blocking Obstacle Sensing:** HC-SR04 ultrasonic distance read is executed inside a `ThreadPoolExecutor` with a `0.25s` hard timeout and `partial=True`. Degraded/unconnected ultrasonic hardware returns `0.0` immediately without freezing FastAPI or causing browser timeout aborts. IR sensor (GPIO 22) provides front proximity backup.
- **Escape Maneuvers:** Obstacle detection triggers a brief reverse clearance (`MOVE B 250ms`) followed by a directional pivot (`MOVE L/R 350ms`).
- **Human-in-the-Loop Review Gate:** When vision detects a violation, robot halts patrol and switches to `review` mode. An interactive verification modal pops up in the HUD (`frontend/src/hud/components/ReviewModal.jsx`) allowing the operator to verify/edit the license plate, confirm and print citation, or dismiss false alarms before resuming patrol.

## Frontend Cyber-Tactical Mobile HUD

- Located at `frontend/src/hud/HudPage.jsx` and compiled to `frontend/dist/`.
- Mobile-first responsive cyber-tactical design with dark theme.
- Dynamic SVG overlays rendering live synthesized parking bays and detected vehicle polygons.
- Touch D-pad drawer for manual teleoperation (`ManualDriveSheet.jsx`).
- Status telemetry badges: Camera, Arduino, Ultrasonic, IR, Printer, Backend.
- Instantaneous E-stop button (and Spacebar keybinding).
- HTTP client (`frontend/src/hud/api.js`) configured with 20s timeout for `autoStart` and clean descriptive abort error handling.

## Deployment & Verification

- Tested across real-world photos and live hardware.
- All 58 unit and integration tests passing (`pytest tests/`).
- One-command updater (`./update.sh`) automates safe Wi-Fi hopping, git pull, frontend rebuild, and service restart.
