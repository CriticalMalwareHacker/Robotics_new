# ParkSensei

## Intelligent Autonomous Parking Monitoring & Enforcement Robot

**ParkSensei** is an embedded edge-computing robotics system designed for smart parking monitoring, vehicle compliance verification, and on-the-spot physical violation ticketing. 

The system pairs a **Raspberry Pi 5** (hosting computer vision, plate OCR, and a FastAPI/React operator HUD) with an **Arduino Uno** and **Adafruit Motor Shield V1** driving a 4WD skid-steer chassis. Equipped with front ultrasonic and infrared proximity sensors, an overhead/onboard optical camera, and an integrated 58 mm thermal receipt printer, ParkSensei detects illegal parking, bay straddling, and misaligned vehicles, prints citations on the spot, and can be teleoperated or run autonomously.

---

## Team Members

- **Pranshu**
- **Jash**
- **Tanay**
- **Krish**
- **Division F**

---

## Key Features

1. **Dynamic Computer Vision Parking Inspection:**
   - **Dynamic Marker Line Detection:** Automatically identifies drawn black divider lines and synthesizes $N$ dynamic parking bays (`BAY-1`, `BAY-2`, `BAY-3`...) without hardcoded coordinates.
   - **Multi-Color Vehicle Card Detection:** Accurately isolates red, yellow, black, and other colored vehicles on the parking mat.
   - **Tight Perspective Quadrilateral Fitting:** Uses multi-scale polygon approximation on convex hulls to hug trapezoidal perspective boundaries tightly with zero excess padding.
   - **Independent Contour Processing:** Prevents adjacent vehicles in neighboring bays from merging across divider lines.
   - Categorizes parking states into: `LEGAL`, `STRADDLING` (line crossing), `WRONG_ORIENTATION` (relative to bay axis), and `OUTSIDE_SLOT`.
2. **Offline License Plate Recognition (OCR):**
   - On-device CPU inference using **RapidOCR** (ONNX Runtime) to extract handwritten and printed vehicle registration numbers (e.g. `MH47AX5364`).
3. **Physical Thermal Citation with Scannable QR Verification:**
   - Onboard **58 mm Thermal Receipt Printer** (ESC/POS protocol, 384 dots/line).
   - Generates high-contrast monochrome violation notices complete with date, time, vehicle ID, plate number, bay ID, and violation reason.
   - **Real Scannable QR Code:** Centered 148×148 px high-contrast QR code at the bottom of the physical ticket. Scanning with any smartphone camera opens the digital ticket record and vehicle photo evidence portal (`/history?ticket=...`).
   - Built with a 36 px bottom tear buffer to prevent physical printer cutters or tear bars from clipping the QR code or disclaimer.
4. **Automated Photographic Evidence Capture:**
   - Whenever a citation is issued, the system captures an optical camera snapshot and overlays:
     - **Bay lines:** Translucent red highlight for the violated bay, green boundaries for compliant bays.
     - **Vehicle quad:** Neon yellow/orange bounding quad with corner vertex markers and vehicle license badge.
     - **Cyber HUD banners:** Top and bottom telemetry bars displaying ticket number, timestamp, bay ID, and violation type.
   - Saved as high-definition JPEG (`evidence_<number>.jpg`) and dual-persisted to SQLite database (`ticket_records` table) and JSON history.
5. **Photo Evidence Gallery (`/history`):**
   - Evaluators and operators can navigate to `/history` on mobile or desktop to explore all issued citations.
   - Includes real-time plate/ticket search, infraction filter chips, and an interactive **Evidence Modal** comparing the optical camera evidence snapshot with the physical thermal receipt.
6. **Autonomous Patrol & Smart Obstacle Avoidance:**
   - Multi-sensor safety stack: **HC-SR04 ultrasonic rangefinder** and **HW-201 active-low IR proximity sensor**.
   - **Non-blocking sensor executor:** 0.25s hard timeout ensures degraded/unconnected sensors never block the application or cause timeouts.
   - Automatic reverse-before-turn clearance (`MOVE B 250ms`) to prevent chassis scraping, followed by timed escape pivots.
7. **Human-in-the-Loop Verification Gate:**
   - Robot halts patrol automatically upon detecting violations.
   - Interactive modal pops up on the mobile HUD allowing operator verification, license plate editing/correction, citation printing, or dismissal.
8. **Mobile-First Cyber-Tactical Heads-Up Display (HUD):**
   - Self-hosted on the Raspberry Pi local network (`10.42.0.1:8000/hud`).
   - Live video stream with dynamic vector polygon overlays, telemetry health badges, touch D-pad manual steering, and instantaneous emergency stop.

---

## System Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │      Mobile-First React + Vite HUD           │
                       │ (/hud, /history, Live SVG Overlays, D-Pad)   │
                       └──────────────────────┬───────────────────────┘
                                              │ HTTP / SSE / Stream
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               Raspberry Pi 5 (Edge Host)                                    │
│  FastAPI Backend (app/main.py)                                                              │
│                                                                                             │
│  ┌───────────────────────┐   ┌───────────────────────────────┐   ┌────────────────────────┐ │
│  │ Dynamic Vision Core   │   │   Autonomous Patrol Manager   │   │   Ticket & Thermal     │ │
│  │ (backend/services/    │   │   (app/api/robot_routes.py)   │   │   Printer Service      │ │
│  │   parking/)           │   │                               │   │   (384 px ESC/POS)     │ │
│  │ - Dynamic Line & Bay  │   │ - State Machine (Auto/Review) │   │ - Pillow Raster Layout │ │
│  │ - Tight Quad Fitting  │   │ - Non-blocking Sensor Reader  │   │ - Bluetooth RFCOMM/SPP │ │
│  │ - RapidOCR ONNX Plate │   │ - Safety Timeout Leases       │   └───────────┬────────────┘ │
│  └───────────▲───────────┘   └──────────────┬────────────────┘               │              │
│              │                              │                                │              │
│  ┌───────────┴───────────┐   ┌──────────────┴────────────────┐               │              │
│  │ USB Camera (/dev/     │   │ Pi GPIO Sensors (gpiozero):   │               │              │
│  │   video1)             │   │ - HC-SR04 Echo/Trig (GPIO 6/5)│               │              │
│  │ 640x480 / 1280x720    │   │ - HW-201 IR (GPIO 22)         │               │              │
│  └───────────────────────┘   └───────────────────────────────┘               │              │
│                                             │ USB Serial (115200 baud)       │ Bluetooth    │
└─────────────────────────────────────────────┼────────────────────────────────┼──────────────┘
                                              ▼                                ▼
                        ┌───────────────────────────────┐      ┌────────────────────────┐
                        │      Arduino Uno Controller   │      │ 58mm Thermal Printer   │
                        │ + Adafruit Motor Shield V1    │      │ (POSIFLOW 58D / Hoin)  │
                        │ M1+M3: Left | M2+M4: Right    │      │ (Bluetooth Wireless)   │
                        └───────────────────────────────┘      └────────────────────────┘
```

---

## Hardware Specifications & Wiring

| Subsystem | Component | Interface & Pins | Details |
| :--- | :--- | :--- | :--- |
| **Brain / Compute** | Raspberry Pi 5 (8 GB) | Debian Linux (Bookworm) | Runs FastAPI, OpenCV, RapidOCR, and GPIO Zero. Powered by **Mi 20,000mAh Power Bank** (5V USB-C PD). |
| **Microcontroller** | Arduino Uno R3 | USB Serial (115200 baud) | Interprets leased motor commands; runs hardware watchdog. |
| **Motor Driver** | Adafruit Motor Shield V1 | Dual L293D H-Bridges | Channels: M1+M3 Left, M2+M4 Right. Powered by **dedicated external Battery Pack** for high torque & faster wheel speeds. |
| **Motors** | 4 × TT Geared DC Motors | 4WD Skid-Steer | PWM calibrated to 255 for reliable loaded start under chassis weight. |
| **Enclosure** | Custom Acrylic Enclosure | 3-Sided (Top, Left, Right) | Front & Back deliberately open for sensor line-of-sight, thermal ticket ejection, and thermal ventilation. |
| **Vision Sensor** | **Hikvision HD USB Webcam** | USB 2.0 / 3.0 | Real-time MJPEG feed at 640×480 or 1280×720 resolution mounted at front. |
| **Ultrasonic Sensor**| HC-SR04 | Pi GPIO 5 (Trig), GPIO 6 (Echo) | Mounted ahead. **Requires voltage divider on Echo** (1 kΩ to GPIO 6, 2 kΩ to GND) to protect 3.3V Pi logic. |
| **Infrared Sensor** | HW-201 Digital IR | Pi GPIO 22 (Out), 3.3V, GND | Mounted ahead. Active-low binary proximity sensor for close-range front obstacles. |
| **Citation Printer** | SHREYANS POSIFLOW 58D | **Bluetooth Wireless** (RFCOMM/SPP) | Direct-thermal 203 DPI, 384 dots wide, ESC/POS raster output with scannable QR verification code. Wirelessly connected to Pi 5 to prevent cable tangling during skid-steer turns. |
| **Demo Apparatus** | White Paper Mat & Cards | Tabletop / Floor setup | White paper with drawn marker bays, colored vehicle cards with plate stickers, and test obstacles (shoe box, bottle). |

---

## Arduino Serial Protocol (115200 Baud)

Communication between the Raspberry Pi and the Arduino Uno uses newline-delimited ASCII strings:

```text
PING                         -> PONG
MOVE <F|B|L|R> <pwm> <ms>   -> OK MOVE
STOP                         -> OK STOP
ESTOP                        -> OK ESTOP (latched until CLEAR)
CLEAR                        -> OK CLEAR
STATUS                       -> STATUS IDLE|MOVING|ESTOP
```

* **Safety Leases:** Every movement command is clamped between 100 ms and 500 ms. If the serial stream stops, the Arduino automatically cuts power to all motors within 500 ms.
* **Skid-Steer Counter-Rotation:** `L` rotates the left motors backward and right motors forward; `R` rotates left forward and right backward.

---

## Parking Violation Rules & Classification

Vehicles detected by the OpenCV vision pipeline are dynamically analyzed against synthesized parking bays:

1. **`STRADDLING`:** Vehicle polygon crosses any interior divider marker line between bays or overlaps multiple bays simultaneously.
2. **`WRONG_ORIENTATION`:** Vehicle driving axis deviates by $> 25^\circ$ from the target parking bay's orientation vector.
3. **`OUTSIDE_SLOT`:** Vehicle centroid or significant area lies outside designated parking bays.
4. **`LEGAL`:** Vehicle is properly bounded and aligned inside a single parking bay.

---

## Repository Structure

```text
Robotics_new/
├── app/
│   ├── main.py                     # FastAPI application setup and routing
│   ├── api/
│   │   ├── robot_routes.py         # Autonomous patrol loop, non-blocking sensors, drive, review endpoints
│   │   ├── parking_routes.py       # Parking monitor, MJPEG camera stream, and frame endpoints
│   │   └── hud_routes.py           # Unified HUD telemetry endpoint & ticket printing
│   ├── hardware/
│   │   └── arduino_serial.py       # USB-Serial driver & handshake protocol
│   └── services/
│       ├── camera.py               # UVC OpenCV camera capture and caching
│       └── printer.py              # ESC/POS raster encoding & printer transport
├── arduino/
│   └── park_sensei_serial/
│       └── park_sensei_serial.ino  # Motor Shield firmware with safety leases
├── backend/
│   └── services/parking/
│       ├── dynamic_detector.py     # Marker line & bay detector, tight perspective quads, relative violations
│       ├── vehicle_detector.py     # Classical fallback detector
│       ├── parking_geometry.py     # Geometry helpers & temporal violation debouncer
│       ├── analyzer.py             # Matches detected vehicles to slot polygons
│       ├── plate_reader.py         # RapidOCR license plate reader
│       ├── ticket.py               # 384 px thermal citation raster layout & history
│       └── monitor.py              # Vision monitor loop (dynamic -> classical fallback)
├── frontend/                       # React 18 + Vite HUD Dashboard
│   ├── src/
│   │   ├── App.jsx                 # Portal navigation & ticket history
│   │   └── hud/
│   │       ├── HudPage.jsx         # Main robot operator interface
│   │       ├── api.js              # Typed HTTP client with safe timeout & abort handling
│   │       └── components/         # ReviewModal, ControlsBar, ManualDriveSheet, CameraFeed, TopBar
├── deploy/                         # Systemd service, serial docs, hotspot setup
├── docs/
│   ├── PARK_SENSEI_GUIDE.md        # Comprehensive system guide and handoff notes
│   ├── PARK_SENSEI_ES_MINI_PROJECT_REPORT.md # Academic embedded systems report
│   └── VISION_NOTES.md             # Vision pipeline analysis and trade-offs
├── update.sh                       # One-command Pi updater with fail-safe Wi-Fi hopping
└── requirements.txt                # Python dependencies
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend development)
- Arduino IDE (to compile and flash `arduino/park_sensei_serial/park_sensei_serial.ino`)

### 2. Backend Installation
```bash
# Clone the repository
git clone https://github.com/CriticalMalwareHacker/Robotics_new.git
cd Robotics_new

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Installation & Build
```bash
cd frontend
npm install
npm run build
cd ..
```
*Note: The built frontend files are automatically served by FastAPI from `frontend/dist` for offline deployment on the Raspberry Pi.*

### 4. Running Locally
```bash
# Start backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open [http://localhost:8000/hud](http://localhost:8000/hud) in your browser.

---

## Raspberry Pi Deployment

On the Raspberry Pi 5, the service runs automatically via systemd:

```bash
# Check service status
sudo systemctl status printsensei-robot --no-pager

# Restart service after updates
sudo systemctl restart printsensei-robot

# View live system logs
sudo journalctl -u printsensei-robot -f
```

### One-Command Updater (`update.sh`)
Because the Pi's Wi-Fi hotspot (`PrintSensei` on `10.42.0.1`) does not have an internet uplink, a fail-safe updater script is included:

```bash
cd ~/Robotics_new
./update.sh
```

This script:
1. Temporarily connects to your Wi-Fi network (configured for `Airtel_Zerotouch_5G`).
2. Pulls the latest commits from the `robotics` branch on GitHub.
3. Restarts the `printsensei-robot` systemd service.
4. **Guarantees that the `PrintSensei` hotspot is restored upon completion**, even if an error or interruption occurs.

---

## Safety Guidelines

- **Bench Testing First:** Always test motor control with the vehicle's wheels elevated off the surface before placing the robot on the tabletop or floor.
- **Dedicated Motor Power:** Always power the Adafruit Motor Shield from an external battery pack. **Never** power DC motors directly from the Arduino or Raspberry Pi USB ports.
- **Hardware Emergency Stop:** Maintain a physical battery power switch within reach at all times during testing.

---

## License

This project is developed for academic and engineering demonstration purposes.
