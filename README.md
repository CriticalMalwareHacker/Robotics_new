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

1. **Computer Vision Parking Inspection:**
   - Real-world metric planar homography mapping a $60 \times 45\text{ cm}$ parking area directly to camera pixel coordinates.
   - Real-time vehicle detection and bounding geometry classification.
   - Categorizes parking states into: `LEGAL`, `OUTSIDE_SLOT`, `STRADDLING`, `WRONG_ORIENTATION`, and `NO_PARKING_ZONE`.
2. **Offline License Plate Recognition (OCR):**
   - On-device CPU inference using **RapidOCR** (ONNX Runtime) to extract vehicle registration numbers.
3. **Physical Thermal Citation Issuance:**
   - Onboard **58 mm Thermal Receipt Printer** (ESC/POS protocol, 384 dots/line).
   - Generates high-contrast monochrome violation notices complete with date, time, vehicle ID, plate number, bay ID, and violation reason.
4. **Autonomous Patrol & Smart Obstacle Avoidance:**
   - Multi-sensor safety stack: **HC-SR04 ultrasonic rangefinder** and **HW-201 active-low IR proximity sensor**.
   - Automatic reverse-before-turn clearance to prevent chassis scraping.
   - Persistent obstacle avoidance maneuvers and auto-stop fail-safe.
5. **Interactive Web Heads-Up Display (HUD):**
   - Self-hosted on the Raspberry Pi local network (`10.42.0.1`).
   - Live camera stream with vector bounding polygon overlays, telemetry gauges, manual teleoperation controls, review verification gate, and emergency stop banner.

---

## System Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │           React + Vite Frontend              │
                       │   (/hud, /history, Live SVG Overlays)        │
                       └──────────────────────┬───────────────────────┘
                                              │ HTTP / SSE / Stream
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               Raspberry Pi 5 (Edge Host)                                    │
│  FastAPI Backend (app/main.py)                                                              │
│                                                                                             │
│  ┌───────────────────────┐   ┌───────────────────────────────┐   ┌────────────────────────┐ │
│  │ Vision & Parking Core │   │   Autonomous Patrol Manager   │   │   Ticket & Thermal     │ │
│  │ (backend/services/    │   │   (app/api/robot_routes.py)   │   │   Printer Service      │ │
│  │   parking/)           │   │                               │   │   (384 px ESC/POS)     │ │
│  │ - Color/Blob Detector │   │ - State Machine (Auto/Review) │   │ - Pillow Layout        │ │
│  │ - Homography (slots)  │   │ - Obstacle Avoidance (L/R)    │   │ - USB/BT /dev/usb/lp0  │ │
│  │ - RapidOCR ONNX Plate │   │ - Safety Timeout Leases       │   └───────────┬────────────┘ │
│  └───────────▲───────────┘   └──────────────┬────────────────┘               │              │
│              │                              │                                │              │
│  ┌───────────┴───────────┐   ┌──────────────┴────────────────┐               │              │
│  │ USB Camera (/dev/     │   │ Pi GPIO Sensors (gpiozero):   │               │              │
│  │   video1)             │   │ - HC-SR04 Echo/Trig (GPIO 6/5)│               │              │
│  │ 640x480 / 1280x720    │   │ - HW-201 IR (GPIO 22)         │               │              │
│  └───────────────────────┘   └───────────────────────────────┘               │              │
│                                             │ USB Serial (115200 baud)       │              │
└─────────────────────────────────────────────┼────────────────────────────────┼──────────────┘
                                              ▼                                ▼
                        ┌───────────────────────────────┐      ┌────────────────────────┐
                        │      Arduino Uno Controller   │      │ 58mm Thermal Printer   │
                        │ + Adafruit Motor Shield V1    │      │ (POSIFLOW 58D / Hoin)  │
                        │ M1+M3: Left | M2+M4: Right    │      └────────────────────────┘
                        └───────────────────────────────┘
```

---

## Hardware Specifications & Wiring

| Subsystem | Component | Interface & Pins | Details |
| :--- | :--- | :--- | :--- |
| **Brain / Compute** | Raspberry Pi 5 (8 GB) | Debian Linux (Bookworm) | Runs FastAPI, OpenCV, RapidOCR, and GPIO Zero. |
| **Microcontroller** | Arduino Uno R3 | USB Serial (115200 baud) | Interprets leased motor commands; runs hardware watchdog. |
| **Motor Driver** | Adafruit Motor Shield V1 | Dual L293D H-Bridges | Channels: M1+M3 Left, M2+M4 Right. Powered by external battery pack. |
| **Motors** | 4 × TT Geared DC Motors | 4WD Skid-Steer | PWM calibrated to 255 for reliable loaded start. |
| **Ultrasonic Sensor**| HC-SR04 | Pi GPIO 5 (Trig), GPIO 6 (Echo) | **Requires voltage divider on Echo** (1 kΩ to GPIO 6, 2 kΩ to GND) to protect 3.3V Pi logic. |
| **Infrared Sensor** | HW-201 Digital IR | Pi GPIO 22 (Out), 3.3V, GND | Active-low binary proximity sensor for close-range front obstacles. |
| **Vision Sensor** | USB UVC Camera | USB 2.0 / 3.0 | Real-time MJPEG feed at 640×480 or 1280×720 resolution. |
| **Citation Printer** | SHREYANS POSIFLOW 58D | USB `/dev/usb/lp0` / BT | Direct-thermal 203 DPI, 384 dots wide, ESC/POS raster output. |

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

Vehicles detected by the OpenCV vision pipeline are mapped through the calibration homography and classified against slot definitions in `backend/services/parking/config/slots.json`:

1. **`NO_PARKING_ZONE`:** Vehicle overlaps by $\ge 10\%$ with a designated restricted / no-parking zone.
2. **`STRADDLING`:** Vehicle occupies $\ge 15\%$ across two different parking bays.
3. **`OUTSIDE_SLOT`:** Overlap with the nearest parking bay is $< 80\%$.
4. **`WRONG_ORIENTATION`:** Vehicle is within the slot ($\ge 80\%$), but its heading angle differs by $> 25^\circ$ from the bay's axis.
5. **`LEGAL`:** Vehicle is properly centered and aligned inside an authorized bay.

---

## Repository Structure

```text
Robotics_new/
├── app/
│   ├── main.py                     # FastAPI application setup and routing
│   ├── api/
│   │   ├── robot_routes.py         # Autonomous patrol loop, manual drive, E-stop, review endpoints
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
│       ├── vehicle_detector.py     # Classical HSV segmentation & contour detection
│       ├── parking_geometry.py     # Planar geometry, polygon intersection, violation debouncing
│       ├── analyzer.py             # Matches detected vehicles to slot polygons
│       ├── plate_reader.py         # RapidOCR license plate reader
│       ├── ticket.py               # 384 px thermal citation raster layout & history
│       └── config/slots.json       # Tabletop metric calibration & slot polygons
├── frontend/                       # React 18 + Vite HUD Dashboard
│   ├── src/
│   │   ├── App.jsx                 # Portal navigation & ticket history
│   │   └── hud/
│   │       ├── HudPage.jsx         # Main robot operator interface
│   │       └── components/         # Telemetry badges, video stream overlay, controls
├── deploy/                         # Systemd service, serial docs, hotspot setup
├── docs/
│   ├── PARK_SENSEI_GUIDE.md        # Comprehensive system guide and handoff notes
│   └── PARK_SENSEI_ES_MINI_PROJECT_REPORT.md # Academic embedded systems report
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
1. Temporarily connects to your Wi-Fi network (configured for `Airtel_8994`).
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
