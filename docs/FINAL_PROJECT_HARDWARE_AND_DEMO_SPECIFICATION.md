# ParkSensei: Complete Hardware, Electrical & Demonstration Specification

**Document Version:** 1.0 (Final Project Edition)  
**Project Title:** ParkSensei — Autonomous Edge-AI Parking Monitoring, Inspection & Enforcement Robot  
**Target Platform:** Raspberry Pi 5 (8 GB) + Arduino Uno R3 (ATmega328P)  
**Authoring Team:** Pranshu, Jash, Tanay, Krish (Division F)  

---

## 1. Executive Summary & System Architecture

**ParkSensei** is a mobile embedded robotic platform designed for automated parking lot surveying, infraction detection, and instantaneous physical citation issuance. The system implements a distributed master-slave embedded computing architecture:

- **High-Level Intelligence (Master):** **Raspberry Pi 5 (8 GB)** executes the core FastAPI application server, real-time OpenCV dynamic computer vision pipeline, RapidOCR license plate recognition engine, and hosts the self-contained cyber-tactical web Heads-Up Display (HUD).
- **Low-Level Motion & Safety (Slave):** **Arduino Uno R3** equipped with an **Adafruit Motor Shield V1** drives a 4WD skid-steer chassis via leased, watchdog-protected PWM commands over high-speed USB CDC serial (115200 baud).
- **Perception Array:** Tri-sensor front array comprising a **Hikvision HD USB Webcam**, an **HC-SR04 Ultrasonic Rangefinder**, and an **HW-201 Infrared (IR) Proximity Sensor**, all wired directly into the Raspberry Pi 5.
- **Physical Enforcement:** Onboard **58 mm Direct-Thermal Receipt Printer** generating physical violation notices with high-contrast, scannable QR verification codes linking directly to a digital photographic evidence gallery (`/history`).

```
                              ┌──────────────────────────────────────────────┐
                              │     Operator Web HUD (Mobile / Desktop)      │
                              │   Teleoperation, Live Stream, Verification   │
                              └──────────────────────┬───────────────────────┘
                                                     │ HTTP / WebSockets
                                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Raspberry Pi 5 (Master Host)                                    │
│  [POWER: Mi 20,000mAh Power Bank (5V USB-C PD)]                                                    │
│                                                                                                    │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐    ┌───────────────────────────┐  │
│  │   Computer Vision Core  │    │  Autonomous Patrol Manager   │    │   Thermal Citation System │  │
│  │   - Dynamic Marker Bays │    │  - Obstacle Stop & Avoidance │    │   - ESC/POS 384 px Raster │  │
│  │   - Multi-Color Cards   │    │  - Verification Review Gate  │    │   - Scannable QR Code     │  │
│  │   - RapidOCR ONNX Engine│    │  - Non-blocking Sensor Loop  │    │   - Evidence Photo Logger │  │
│  └────────────▲────────────┘    └──────────────┬───────────────┘    └─────────────┬─────────────┘  │
│               │                                │                                  │                │
│  ┌────────────┴────────────┐    ┌──────────────┴───────────────┐                  │                │
│  │  Hikvision HD Webcam    │    │  Front Pi GPIO Sensors:      │                  │                │
│  │  (USB 2.0 /dev/video1)  │    │  - HC-SR04 Sonar (GPIO 5/6)  │                  │                │
│  │  Wide-angle mat view    │    │  - HW-201 IR Beam (GPIO 22)  │                  │                │
│  └─────────────────────────┘    └──────────────────────────────┘                  │                │
│                                                │ USB Serial (115200 baud)         │ Bluetooth RFCOMM
└────────────────────────────────────────────────┼──────────────────────────────────┼────────────────┘
                                                 ▼                                  ▼
                         ┌───────────────────────────────────────┐  ┌────────────────────────────────┐
                         │       Arduino Uno R3 + Motor Shield   │  │  58 mm Thermal Receipt Printer │
                         │  [POWER: Dedicated Battery Pack]      │  │  (SHREYANS POSIFLOW 58D)       │
                         │  - 4x TT Geared DC Motors (4WD)       │  │  - Wireless Bluetooth SPP      │
                         │  - Leased Watchdog Safety Timer       │  └────────────────────────────────┘
                         └───────────────────────────────────────┘
```

---

## 2. Power Supply & Electrical Distribution

To guarantee high operational stability and prevent common embedded robotics pitfalls (e.g., brownout resets, motor inductive spikes rebooting the single-board computer, or voltage sag under motor load), ParkSensei utilizes **dual electrically isolated power sources**:

| Power Domain | Power Source | Voltage & Current | Target Subsystems | Rationale & Design Choice |
| :--- | :--- | :--- | :--- | :--- |
| **Digital Logic & Compute** | **Mi 20,000mAh Power Bank** | 5.0 V / 3.0 A – 5.0 A (USB-C Power Delivery) | Raspberry Pi 5, Hikvision Webcam, HC-SR04, HW-201, Logic side of Arduino | The Pi 5 requires high-amperage 5V power to sustain quad-core 2.4 GHz compute and camera encoding. The Mi 20,000mAh power bank prevents low-voltage throttling and eliminates brownouts during heavy vision processing. |
| **Inductive Actuation & Drive** | **Dedicated External Battery Pack** | 7.4 V – 9.0 V DC (High discharge) | Adafruit Motor Shield V1 `EXT_PWR`, 4 × TT Geared DC Motors | DC motors produce substantial back-EMF and current surges under chassis load. Powering the motor shield via dedicated battery pack (with the shield's PWR logic jumper disconnected) gives the motors higher voltage and torque, making wheel rotation and skid-steer turns significantly faster and more forceful. |

### Grounding & Surge Isolation Topology
1. The logic power jumper on the Adafruit Motor Shield V1 is **removed**, ensuring complete galvanic separation between the motor driver H-bridge rails and the Arduino's onboard 5V regulator.
2. Ground reference is maintained across the USB CDC serial cable between the Pi 5 and Arduino Uno to ensure unified logic level reference for digital communication without circulating motor noise into the Pi's power planes.

---

## 3. Chassis, Mechanical Drive & Acrylic Enclosure

### 3.1 Chassis & Wheel Arrangement
- **Chassis Base:** Lightweight acrylic robotic smart-car platform with pre-drilled component mounting slots.
- **Drive Kinematics:** 4WD Skid-Steer arrangement utilizing 4 independent TT geared DC motors paired with high-traction rubber wheels.
  - **Left Side:** Motors M1 (Front Left) and M3 (Rear Left) driven synchronously.
  - **Right Side:** Motors M2 (Front Right) and M4 (Rear Right) driven synchronously.
- **Turn Mechanism:** Counter-rotation differential drive (skid-steering):
  - Left Pivot: Left motors reverse, Right motors forward.
  - Right Pivot: Left motors forward, Right motors reverse.

### 3.2 Custom 3-Sided Acrylic Enclosure
The upper deck is protected by a customized transparent acrylic casing designed with a deliberate balance of protection, visibility, and operational functionality:

```
                  ┌──────────────────────────────────────────────┐
                  │                 TOP ACRYLIC                  │
                  │       (Protects Pi 5, Arduino, Wiring)       │
 ┌────────────────┴──────────────────────────────────────────────┴────────────────┐
 │ LEFT ACRYLIC SIDE                                           RIGHT ACRYLIC SIDE │
 │ (Protects Left Motor Wires)                               (Protects Right Wires)│
 │                                                                                │
 │  [FRONT IS OPEN]                                           [BACK IS OPEN]      │
 │  - Hikvision Webcam sightline                              - Thermal ticket    │
 │  - Ultrasonic transducer pulses                              paper exit path   │
 │  - IR proximity optical path                               - Cable / charge access │
 │                                                            - Heat exhaust      │
 └────────────────────────────────────────────────────────────────────────────────┘
```

1. **Covered 3 Sides (Top, Left, Right):**
   - **Top:** Protects the Pi 5 processor deck, Arduino Uno stack, and wiring junctions from physical disturbance, accidental tool drops, and dust.
   - **Left & Right Sides:** Prevents motor wiring harnesses and wheel-well leads from catching on obstacles or exterior barriers during pivots.
2. **Deliberately Open 2 Sides (Front & Back):**
   - **Front Side Open:** Provides completely unobstructed optical sightlines for the Hikvision webcam, allows the HC-SR04 ultrasonic transducer to emit and receive 40 kHz pulses without echo reflection, and ensures the HW-201 IR emitter/photodiode pair operates without acrylic refractive distortion.
   - **Back Side Open:** Enables clean, unobstructed vertical/rear paper ejection from the 58 mm thermal receipt printer; allows rapid USB / battery recharging access; and acts as an exhaust port for active airflow across the Pi 5 heatsink.

---

## 4. Front Perception & Sensor Suite (Direct to Raspberry Pi 5)

All three front perception devices are mounted ahead on the front chassis and interface directly with the Raspberry Pi 5:

```
                 FRONT CHASSIS BUMPER
┌────────────────────────────────────────────────────────┐
│   [ HW-201 IR ]     [ HIKVISION WEBCAM ]    [ HC-SR04 ]│
│    Active-Low         Wide-Angle Optical     40kHz Ping│
│    Ground Beam            Mat Vision         Sonar Cone│
└────────┬──────────────────────┬───────────────────┬────┘
         │ GPIO 22              │ USB 2.0           │ GPIO 5/6 (Divider)
         ▼                      ▼                   ▼
┌────────────────────────────────────────────────────────┐
│                 Raspberry Pi 5 GPIO & USB              │
└────────────────────────────────────────────────────────┘
```

### 4.1 Sensor Technical Specifications & Pinouts

| Device | Type & Model | Mounting Location | Pi 5 Physical Pin | Pi 5 BCM GPIO | Interface / Signal Characteristics |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vision Camera** | **Hikvision HD USB Webcam** | Front center, angled $35^\circ$ down toward ground | USB Port | USB Bus | UVC compliant, 30 FPS, hardware MJPEG, wide-angle lens focused on parking mat. |
| **Ultrasonic Rangefinder** | **HC-SR04** | Front right | Pin 2 (5V VCC)<br>Pin 14 (GND)<br>Pin 29 (TRIG)<br>Pin 31 (ECHO) | GPIO 5 (TRIG)<br>GPIO 6 (ECHO) | High-precision sonic distance measurement (2 cm – 400 cm). **ECHO pin uses a 1 kΩ / 2 kΩ resistor voltage divider** stepping 5V down to 3.3V to safeguard Pi GPIOs. |
| **Infrared Proximity** | **HW-201 Digital IR** | Front left | Pin 1 (3.3V VCC)<br>Pin 6 (GND)<br>Pin 15 (OUT) | GPIO 22 (OUT) | Active-low binary infrared proximity beam with onboard comparator and sensitivity trimpot for immediate close-range obstacle halt. |

### 4.2 HC-SR04 Voltage Divider Schematic
Because the HC-SR04 operates at 5V, its `ECHO` output delivers a 5V logic pulse that would damage the Raspberry Pi's 3.3V-tolerant GPIO pins. The voltage divider is implemented as follows:

```
  HC-SR04 ECHO (5V Pulse)
            │
            ▼
        [ 1 kΩ Resistor ]
            │
            ├───────────────► Connected to Pi BCM GPIO 6 (Safe 3.3V Logic Level)
            │
        [ 2 kΩ Resistor ]
            │
            ▼
        Ground (GND)
```

$$\text{Voltage at GPIO 6} = 5.0\,\text{V} \times \left(\frac{2\,\text{k}\Omega}{1\,\text{k}\Omega + 2\,\text{k}\Omega}\right) = 3.33\,\text{V}$$

---

## 5. Actuation, Firmware & Safety Watchdog (Arduino Uno)

### 5.1 Arduino Uno R3 & Adafruit Motor Shield V1
- Dedicated microcontroller offloads time-critical PWM wave generation from Linux.
- Dual L293D motor driver chips provide 4 H-bridge channels supporting up to 0.6 A continuous (1.2 A peak) per channel.
- Channels:
  - **M1:** Front Left Motor
  - **M2:** Front Right Motor
  - **M3:** Rear Left Motor
  - **M4:** Rear Right Motor

### 5.2 ASCII Command Protocol (115200 Baud)
All commands between the Pi 5 and Arduino Uno are newline-delimited ASCII strings:

```text
PING                         -> PONG
MOVE <Direction> <PWM> <ms>  -> OK MOVE
STOP                         -> OK STOP
ESTOP                        -> OK ESTOP (Hardware safety latch)
CLEAR                        -> OK CLEAR (Releases E-stop latch)
STATUS                       -> STATUS IDLE|MOVING|ESTOP
```

### 5.3 Lease-Based Watchdog Safety Architecture
To prevent runaway robot conditions caused by software crashes, network lag, or disconnected cables:
- Every `MOVE` command specifies a strict lease duration (clamped between 100 ms and 500 ms).
- The Arduino microcontroller maintains an internal hardware millisecond timer (`millis()`).
- When the lease expires, the Arduino firmware automatically calls `stopMotors()` (`RELEASE` on all 4 channels) unless a fresh lease is renewed by the Pi 5.
- An instantaneous hardware E-stop command (`ESTOP`) latches the Arduino in a safe halt state until an explicit operator `CLEAR` command is received.

---

## 6. Onboard Thermal Citation Ticketing System

### 6.1 Hardware Specifications & Wireless Interface
- **Model:** SHREYANS POSIFLOW 58D (or Hoin 58 mm compatible thermal receipt printer).
- **Mechanism:** Direct-thermal line printing (no ink ribbons or toner cartridges required).
- **Resolution:** 203 DPI (8 dots/mm, 384 dots per line).
- **Wireless Interface:** **Bluetooth Wireless (RFCOMM / Serial Port Profile - SPP)**.
  - Wirelessly paired to Raspberry Pi 5 onboard Bluetooth 5.0 controller.
  - Exposed on Linux as `/dev/rfcomm0` character device node or directly communicated via Python `AF_BLUETOOTH` stream socket on RFCOMM channel 1.
  - Protocol: Standard ESC/POS binary raster protocol (`GS v 0` command).
- **Engineering Advantages of Wireless Bluetooth Printing:**
  1. **Zero Cable Snagging:** Eliminates trailing or looping USB cables that could catch on wheels, snag on obstacles, or bind during $360^\circ$ skid-steer counter-rotating pivots.
  2. **USB Bus Bandwidth Allocation:** Keeps the Raspberry Pi 5 USB 3.0/2.0 high-speed bus dedicated strictly to the Hikvision optical webcam video stream and Arduino serial interface without bus contention.
  3. **Vibration Isolation:** Mechanically decouples printer paper-tearing tension and roll motor vibrations from the Raspberry Pi 5 compute board.

### 6.2 Citation Receipt Design & Scannable QR Code
The citation receipt is dynamically compiled in memory as a 384 px wide monochrome bitmap:
1. **Header:** High-visibility banner `[ OFFICIAL PARKING CITATION ]`.
2. **Metadata:** Ticket serial number (e.g., `T-261019-001`), timestamp, assigned bay ID (`BAY-2`), and specific infraction type (`STRADDLING`, `WRONG_ORIENTATION`, or `OUTSIDE_SLOT`).
3. **Plate Badge:** High-contrast bordered box displaying the verified registration plate (e.g., `MH EF 4752`).
4. **Scannable QR Verification Code:** A high-contrast 148×148 px QR code positioned at the bottom of the ticket. When scanned by an evaluator's smartphone, it instantly opens the live digital citation portal (`/history?ticket=<number>`).
5. **Photo Evidence Capture:** Concurrently, an annotated optical snapshot with cyber-HUD telemetry banners and bay overlay polygons is generated and stored in the SQLite database and JSON evidence vault.

---

## 7. Demonstration, Testing & Evaluation Environment

The physical demonstration environment was engineered to replicate a scaled real-world parking lot:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DEMONSTRATION TEST SURFACE                           │
│                                                                        │
│   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐         │
│   │     BAY-1      │   │     BAY-2      │   │     BAY-3      │         │
│   │                │   │  [YELLOW CARD] │   │  [RED CARD]    │         │
│   │     LEGAL      │   │  (Straddling)  │   │  (Wrong Angle) │         │
│   │                │   │ [MH EF 4752]   │   │ [MH01AB1234]   │         │
│   └────────────────┘   └────────────────┘   └────────────────┘         │
│                             ▲                                          │
│   ══════════════════════════╪═══════════════════════════════════════   │
│                 PARKING AISLE / PATROL CORRIDOR                        │
│                                                                        │
│   [START LINE] ───────►  [OBSTACLE: SHOE BOX / BOTTLE]                 │
│      [ROBOT]             (Triggers Sonar/IR Avoidance)                 │
└────────────────────────────────────────────────────────────────────────┘
```

### 7.1 Scaled Parking Mat
- **Base Surface:** Large white heavy-gauge paper sheet forming the high-reflectance parking surface ($S \le 65, V \ge 110$ in HSV color space).
- **Boundary Markings:** High-contrast black marker divider lines drawn orthogonally to define designated parking bays (`BAY-1`, `BAY-2`, `BAY-3`).

### 7.2 Scaled Vehicle Targets
- **Physical Models:** Colored rectangular card stock (yellow, red, black, blue, and green) and small card boxes cut to proportional scale.
- **License Plate Stickers:** Each test vehicle is affixed with an authentic printed vehicle registration sticker (e.g., `MH EF 4752`, `MH 47 AX 5364`, `MH01AB1234`).
- **Violation Scenarios Tested:**
  - **Legal Parking:** Card centered within bay boundaries parallel to marker lines.
  - **Bay Straddling:** Card overlapping a black divider line or intersecting multiple bays.
  - **Wrong Orientation:** Card placed at an angle exceeding $25^\circ$ relative to the bay orientation axis.
  - **Outside Slot:** Card positioned in driving aisles outside designated bays.

### 7.3 Obstacle Avoidance Test Objects
- **Obstacles:** Everyday solid objects including shoe boxes, cardboard boxes, and water bottles placed along the patrol path.
- **Avoidance Sequence:**
  1. Front ultrasonic sensor detects obstacle at $\le 18$ cm or IR beam is broken.
  2. Robot halts immediately (`STOP`).
  3. Robot initiates safety clearance reverse (`MOVE B 255 250ms`).
  4. Robot executes an escape pivot (`MOVE L 255 350ms` or `MOVE R 255 350ms`).
  5. If path is clear, autonomous forward patrol resumes.

---

## 8. Complete Software Stack & Dataflow Architecture

| Layer | Component | Technologies | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **Firmware** | `park_sensei_serial.ino` | C++, `AFMotor.h` | Parses serial commands, enforces 500 ms movement lease watchdog, drives L293D H-bridges. |
| **Backend & API** | FastAPI / Uvicorn | Python 3.11+, Pydantic v2 | Manages robot state machine, non-blocking telemetry loops, REST API, and MJPEG video streaming. |
| **Vision & AI** | Dynamic CV Pipeline | OpenCV, NumPy, RapidOCR | Synthesizes marker bays, fits tight perspective card polygons, classifies infractions, reads plate text. |
| **Print & Evidence**| Ticket Service | Pillow (PIL), SQLite, ESC/POS | Rasterizes 384 px thermal tickets, overlays cyber HUD evidence banners, saves records. |
| **Operator UI** | Tactical HUD | React 18, Vite, Tailwind/CSS | Self-hosted at `http://10.42.0.1:8000/hud`. Provides live feed, interactive verification modal, D-pad steering. |

---

## 9. Hardware Preflight & Verification Checklist

Before starting autonomous patrol or evaluation demos, perform the following verification:

1. **Power Check:**
   - [ ] Mi 20,000mAh Power Bank connected to Raspberry Pi 5 USB-C port (Power LED solid green, no low-voltage lightning bolt).
   - [ ] Motor Battery Pack connected to Motor Shield `EXT_PWR` terminals (Shield LED lit, logic jumper removed).
2. **Serial Link Check:**
   - [ ] Arduino Uno USB cable plugged into Pi 5 USB 3.0 port (`ls -l /dev/serial/by-id/`).
   - [ ] Arduino responds to `PING` with `PONG`.
3. **Perception Check:**
   - [ ] Hikvision webcam recognized at `/dev/video1` (or `/dev/video0`). Live feed visible on HUD.
   - [ ] HC-SR04 ultrasonic rangefinder reading active (distance decreases when hand is placed in front).
   - [ ] HW-201 IR LED toggles and HUD displays `Blocked` when object is within 5 cm.
4. **Thermal Printer Check:**
   - [ ] 58 mm printer powered on and loaded with direct-thermal roll (thermal side facing print head).
   - [ ] Test print verified via HUD `Test Print` button; QR code scans cleanly with phone camera.
5. **Physical Enclosure Check:**
   - [ ] 3-sided acrylic case secured over Top, Left, and Right decks.
   - [ ] Front opening clear of wire obstructions in camera and sensor sightlines.
   - [ ] Rear opening clear for unobstructed paper receipt ejection.
