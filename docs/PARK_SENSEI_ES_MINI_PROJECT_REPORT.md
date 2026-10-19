# MINI PROJECT REPORT
## EMBEDDED SYSTEMS (ES)

---

### 1. Student Details

- **Name of Student(s):** [Insert Name(s), e.g., Tanay Kumar / Pranshu Mangale]
- **Roll Number:** [Insert Roll Number(s)]
- **Program / Semester / Division:** B.Tech / Semester [VI] / Div [A]
- **Course Name:** Embedded Systems (ES)
- **Course Code:** [Insert Course Code, e.g., EC / CS / AI]
- **Faculty Guide:** [Insert Faculty Guide Name]
- **Academic Year:** 2025–2026

---

### 2. Aim

To design, develop, and implement **ParkSensei**, an embedded smart parking enforcement and inspection vehicle. The system integrates an embedded edge computer (Raspberry Pi 5) with a dedicated microcontroller (Arduino Uno + Motor Shield) to provide teleoperated robotic mobility, real-time computer vision-based parking slot violation detection, license plate optical character recognition (OCR), and on-the-spot physical violation ticketing via an onboard 58 mm thermal receipt printer.

---

### 3. Apparatus

#### A. Hardware Components
1. **Single Board Computer (Edge Processor):** Raspberry Pi 5 (8 GB RAM, Quad-core Arm Cortex-A76 @ 2.4 GHz)
   - Powered by a dedicated **Mi 20,000mAh Power Bank** delivering stable, high-amperage 5V USB-C power to eliminate brownouts or CPU frequency throttling.
2. **Microcontroller Unit (Actuator Subsystem):** Arduino Uno R3 (ATmega328P @ 16 MHz)
   - Communicates with Raspberry Pi 5 over USB Serial (115200 baud).
3. **Motor Driver Shield:** Adafruit Motor Shield V1 (Dual L293D H-Bridge Motor Drivers)
   - Powered by a dedicated external **High-Discharge Battery Pack** connected to `EXT_PWR` (logic jumper removed). This provides elevated voltage and instantaneous current, driving the 4 DC motors significantly faster and stronger under chassis load.
4. **DC Motors & Drive System:** 4 × 5V–9V TT Geared DC Motors configured in a 4WD Skid-Steer drive arrangement (M1+M3 Left, M2+M4 Right).
5. **Chassis & Body Enclosure:**
   - 4WD Smart Car robotic chassis platform with high-traction rubber wheels.
   - **Custom Acrylic Case:** Encloses **3 sides: Top, Left, and Right**.
   - **Deliberately Open Front & Back:**
     - **Front Side Open:** Clear, unblocked field-of-view for optical camera and obstacle sensors.
     - **Back Side Open:** Physical ejection of printed thermal tickets, wiring harness access, battery charging, and heat ventilation.
6. **Front Perception & Sensor Suite (All 3 connected directly to Pi 5):**
   - **Optical Vision Sensor:** **Hikvision HD USB Webcam** (UVC compliant, wide-angle lens, angled forward-downward at the parking surface).
   - **Ultrasonic Rangefinder:** **HC-SR04 Ultrasonic Sensor** mounted ahead for mid/long-range collision detection (Pi GPIO5 Trigger, GPIO6 Echo stepped via 1 kΩ / 2 kΩ resistor voltage divider).
   - **Infrared Proximity Sensor:** **HW-201 Digital IR Sensor** mounted ahead for close-range front boundary detection (Pi GPIO22, active-low).
7. **Thermal Citation Printer:** 58 mm Thermal Receipt Printer (POSIFLOW 58D / ESC/POS protocol, 203 DPI, 384 dots/line) connected wirelessly to Raspberry Pi 5 via Bluetooth (RFCOMM / SPP), printing official citations with high-contrast scannable QR verification codes.
8. **Demonstration & Testing Materials:**
   - **Scaled Parking Mat:** White paper surface with high-contrast black marker lines defining designated parking bays (`BAY-1`, `BAY-2`, `BAY-3`).
   - **Vehicle Scale Models:** Different colored rectangular cards (yellow, red, black, blue, green) and boxes, each affixed with real printed vehicle registration plate stickers (e.g. `MH EF 4752`, `MH01AB1234`).
   - **Obstacle Avoidance Test Objects:** Physical everyday obstacles (shoe boxes, bottles) placed in the robot's patrol corridor to test real-time ultrasonic/IR detection, reverse clearance, and escape pivots.
9. **Interfacing & Cabling:** USB Type-A to Type-B Arduino cable, wireless Bluetooth interface for printer (cable-free operation preventing tangling during skid-steer turns), sensor breadboard jumpers, resistor voltage divider network.

#### B. Software Tools & Frameworks
1. **Operating System:** Raspberry Pi OS 64-bit (Debian Bookworm with Linux Kernel 6.6+)
2. **Backend Engine:** Python 3.11+, FastAPI framework, Uvicorn ASGI server
3. **Computer Vision & Image Processing:** OpenCV (`opencv-python`), NumPy, Pillow (PIL)
4. **OCR Engine:** RapidOCR with ONNX Runtime CPU engine for embedded license plate recognition
5. **Firmware:** Arduino C/C++ (`AFMotor.h`), compiled via Arduino IDE / CLI
6. **Web Interface (HUD):** React 18, Vite, Lucide Icons, Tailwind CSS / Vanilla CSS
7. **Communication Protocols:** USB CDC Serial (115200 baud, ASCII newline-delimited command protocol), ESC/POS binary raster printer protocol, HTTP REST & MJPEG video streaming

---

### 4. Theory

#### 4.1 Application & Domain
In modern urban infrastructure, illegal parking, double parking, and bay straddling cause significant congestion and security hazards. Traditional enforcement relies on static CCTV with severe blind spots or manual foot patrols with handheld ticket pads. **ParkSensei** introduces a mobile embedded edge-computing solution: an embedded mobile unit capable of maneuvering through parking aisles, surveying designated parking bays, verifying vehicle compliance through computer vision, and instantly issuing formal thermal citations.

#### 4.2 Working Principle
The system follows a distributed master-slave embedded architecture:

1. **Edge Perception & High-Level Control (Raspberry Pi 5 - Master):**
   - The Pi 5 runs a multi-threaded FastAPI service serving both as the application server and the hardware orchestrator.
   - The video stream captured by the USB camera is calibrated to real-world ground coordinates via planar homography ($\mathbf{H}$ transformation).
   - Vehicles within calibrated parking slots (`A1`, `A2`, `A3`) are segmented via color/morphology detection and analyzed geometrically for boundary compliance (identifying legal parking, slot straddling, wrong orientation, or no-parking zones).
   - When a violation is flagged, the vehicle contour quad is rectified and processed by the RapidOCR engine to extract the license plate registration string.
   - The operator supervises the vehicle through an interactive web-based Heads-Up Display (HUD) hosted directly on the Pi's local network (`10.42.0.1`), enabling teleoperated manual driving and violation ticket dispatch.

2. **Low-Level Motor Actuation (Arduino Uno - Slave):**
   - The Arduino Uno is dedicated exclusively to motor pulse-width modulation (PWM) and timing safety.
   - Over a 115200-baud USB serial link, the Pi issues leased movement commands (`MOVE <Direction> <PWM> <Duration_MS>`).
   - The Arduino parses incoming ASCII commands, sets L293D directional channels via `AFMotor`, and enforces a hardware watchdog timer (100–500 ms). If serial communication drops, all motors stop immediately to prevent runaway.

3. **On-Board Physical Ticketing with Scannable QR Verification:**
   - Once a violation is confirmed, the Pi rasterizes a standardized 384 px monochrome citation image containing the date, violation type, bay ID, license plate, and a high-contrast QR verification code.
   - **Real Scannable QR Code:** Scanning the bottom of the thermal receipt with any smartphone camera instantly directs the evaluator or driver to the digital evidence portal (`/history?ticket=<number>`).
   - The rasterized image is converted into ESC/POS binary raster printer commands (`GS v 0`) and transmitted to the thermal printer wirelessly via Bluetooth RFCOMM socket (channel 1/2) or device node `/dev/rfcomm0`, eliminating trailing wires during robot maneuvering.
   - Simultaneously, an annotated photo evidence snapshot is generated—drawing bay bounds (red violation bay, green compliant bays), vehicle bounding quadrilateral, license plate badge, and cyber HUD telemetry banners—and persisted alongside the citation record in SQLite and JSON databases. Evaluators can review this evidence gallery at `/history`.

```
┌────────────────────────────────────────────────────────┐
│                   Operator HUD (Web)                   │
│         Manual Controls, Video Stream, Actions         │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / WebSockets
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Raspberry Pi 5 (Edge)                  │
│  - FastAPI Web & API Server                            │
│  - Video Capture & Homography Coordinate Mapping       │
│  - Vehicle Detection & Parking Geometry Classifier     │
│  - RapidOCR Plate Text Engine                          │
│  - ESC/POS Thermal Label Formatter                     │
└───────────────┬────────────────────────┬───────────────┘
                │ Serial (115200 baud)   │ Bluetooth RFCOMM / SPP
                ▼                        ▼
┌───────────────────────────────┐ ┌──────────────────────┐
│     Arduino Uno + Shield      │ │ 58mm Thermal Printer │
│  - L293D Motor Channel Control│ │ - Physical Citation  │
│  - 4WD Skid-Steer Kinematics  │ │   Receipt Issuance   │
│  - Lease-based Safety Watchdog│ └──────────────────────┘
└───────────────┬───────────────┘
                ▼
┌───────────────────────────────┐
│     4x Geared DC Motors       │
│  (M1/M3: Left, M2/M4: Right)  │
└───────────────────────────────┘
```

#### 4.3 Major Components & Functionality

1. **Raspberry Pi 5 (Master Computer):**
   - High-performance 64-bit ARM edge computer capable of running lightweight neural networks, OpenCV image pipelines, and RapidOCR plate recognition models concurrently with sub-second response times.
   - Powered by a dedicated **Mi 20,000mAh Power Bank** (5V / 3A–5A USB-C PD) guaranteeing isolated, stable current for the SoC and peripherals.
   - Hosts the offline local network access point (`PrintSensei` SSID) allowing wire-free browser connectivity for the operator console without requiring external internet.

2. **Arduino Uno + Adafruit Motor Shield V1 (Motor Controller):**
   - Offloads real-time PWM pulse generation and motor switching from the Linux OS.
   - Powered by an external **High-Discharge Battery Pack** wired to `EXT_PWR` (with logic jumper disconnected) to give motors higher voltage and torque, significantly boosting wheel rotation speed and turning capability under load.
   - Dual L293D drivers manage bidirectional high-current driving for 4 DC motors grouped by side (M1+M3 Left, M2+M4 Right) to implement skid-steer counter-rotation for sharp turns.

3. **Front Perception Suite (Directly Wired to Raspberry Pi 5):**
   - **Hikvision HD USB Optical Camera:** Wide-angle forward-downward perspective providing live optical frames for dynamic parking line synthesis and vehicle card detection.
   - **HC-SR04 Ultrasonic Sensor:** Measures distance (0–400 cm) to ahead objects via high-frequency sonic pulses; calibrated threshold at $\le 18$ cm halts patrol for obstacle avoidance.
   - **HW-201 Digital IR Sensor:** Provides ultra-fast, close-proximity active-low boundary detection right above ground clearance.

4. **Chassis & 3-Sided Acrylic Enclosure:**
   - 4WD Smart Car robotic chassis housing the motors, stacked Arduino/shield, and Pi 5 electronics.
   - **Custom Acrylic Case:** Encloses the top deck, left side, and right side to safeguard sensitive electronics and wiring harnesses against external interference.
   - **Open Front & Back Design:** Front is uncovered for unrestricted optical camera and ultrasonic/IR sensor sightlines; rear is uncovered for thermal paper ejection, cable access, and thermal ventilation.

5. **SHREYANS POSIFLOW 58D Thermal Printer (Bluetooth Wireless Connection):**
   - High-reliability 58 mm direct-thermal mechanism requiring no ink or ribbon.
   - Connected wirelessly to Raspberry Pi 5 via Bluetooth RFCOMM (Serial Port Profile - SPP), eliminating cable entanglement during 360° skid-steer turns and leaving Pi USB ports dedicated to the Hikvision HD webcam.
   - Uses Floyd-Steinberg dithering algorithms to generate crisp 1-bit monochrome graphics of parking notices and barcodes.
   - Prints a real, scannable QR verification code that resolves to the digital evidence gallery.

---

### 5. Project Photographs & Demonstration Setup

> *Note: Embed clear high-resolution photographs of the physical setup here.*

#### 5.1 Complete System Hardware Assembly
```
+-----------------------------------------------------------+
|                                                           |
|             [ INSERT PHOTOGRAPH HERE:                     |
|        Full Isometric View of ParkSensei Setup            |
|    Showing 4WD Chassis, 3-Sided Acrylic Case (Top/L/R),   |
|     Front Hikvision Webcam & Ultrasonic/IR Sensors,       |
|    Mi 20,000mAh Power Bank, Arduino Shield, and Printer]  |
|                                                           |
+-----------------------------------------------------------+
Figure 1: Complete ParkSensei Hardware Architecture and Mobile Robotic Platform
```

#### 5.2 Top-Down View & Dual Power Distribution
```
+-----------------------------------------------------------+
|                                                           |
|             [ INSERT PHOTOGRAPH HERE:                     |
|           Top-Down View of Electronics Deck               |
|      Showing Arduino Shield Stacking, Motor Battery Pack, |
|    Mi 20,000mAh Pi Power Bank, and Pi 5 GPIO Pinouts]     |
|                                                           |
+-----------------------------------------------------------+
Figure 2: Electronics Deck, Motor Shield Stacking, and Dual Power Isolation
```

#### 5.3 Live Web HUD & Tabletop Demonstration Setup
```
+-----------------------------------------------------------+
|                                                           |
|             [ INSERT PHOTOGRAPH HERE:                     |
|      Test Parking Mat (White Paper with Marker Bays)      |
|     Colored Vehicle Cards with License Plate Stickers     |
|    Test Obstacle (Shoe Box / Bottle) in Front of Robot    |
|   and Operator Laptop/Tablet HUD Displaying Live Feed]    |
|                                                           |
+-----------------------------------------------------------+
Figure 3: Tabletop Parking Test Layout with Active Web HUD and Thermal Receipt Output
```

---

### 6. Code / Firmware

#### 6.1 Arduino Motor Controller Firmware (`park_sensei_serial.ino`)
The firmware enforces strict watchdog timing: all motion commands have a maximum lease of 500 ms, automatically dropping motor power if communication ceases.

```cpp
#include <AFMotor.h>
#include <stdio.h>
#include <string.h>

AF_DCMotor motor1(1); // Left Front
AF_DCMotor motor2(2); // Right Front
AF_DCMotor motor3(3); // Left Rear
AF_DCMotor motor4(4); // Right Rear

const unsigned long MIN_MOVE_MS = 100;
const unsigned long MAX_MOVE_MS = 500;
const int MIN_DRIVE_PWM = 255; // Calibrated torque threshold for 4WD loaded chassis
char lineBuffer[48];
size_t lineLength = 0;
bool estopLatched = false;
bool moving = false;
unsigned long stopAt = 0;

void stopMotors() {
  motor1.run(RELEASE);
  motor2.run(RELEASE);
  motor3.run(RELEASE);
  motor4.run(RELEASE);
  moving = false;
}

void beginMove(char direction, int speed, unsigned long durationMs) {
  if (estopLatched) {
    Serial.println("ERR ESTOP");
    return;
  }
  speed = constrain(speed, 0, 255);
  if (speed == 0) {
    stopMotors();
    Serial.println("OK STOP");
    return;
  }
  if (speed < MIN_DRIVE_PWM) speed = MIN_DRIVE_PWM;
  durationMs = constrain(durationMs, MIN_MOVE_MS, MAX_MOVE_MS);

  motor1.setSpeed(speed); motor2.setSpeed(speed);
  motor3.setSpeed(speed); motor4.setSpeed(speed);

  switch (direction) {
    case 'F': // Forward
      motor1.run(FORWARD); motor3.run(FORWARD);
      motor2.run(FORWARD); motor4.run(FORWARD);
      break;
    case 'B': // Backward
      motor1.run(BACKWARD); motor3.run(BACKWARD);
      motor2.run(BACKWARD); motor4.run(BACKWARD);
      break;
    case 'L': // Skid-Steer Counter-Rotation Left
      motor1.run(BACKWARD); motor3.run(BACKWARD);
      motor2.run(FORWARD);  motor4.run(FORWARD);
      break;
    case 'R': // Skid-Steer Counter-Rotation Right
      motor1.run(FORWARD);  motor3.run(FORWARD);
      motor2.run(BACKWARD); motor4.run(BACKWARD);
      break;
    default:
      stopMotors();
      Serial.println("ERR DIRECTION");
      return;
  }
  moving = true;
  stopAt = millis() + durationMs;
  Serial.println("OK MOVE");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      lineBuffer[lineLength] = '\0';
      if (lineLength > 0) {
        if (strcmp(lineBuffer, "PING") == 0) Serial.println("PONG");
        else if (strcmp(lineBuffer, "STOP") == 0) { stopMotors(); Serial.println("OK STOP"); }
        else if (strcmp(lineBuffer, "ESTOP") == 0) { estopLatched = true; stopMotors(); Serial.println("OK ESTOP"); }
        else if (strcmp(lineBuffer, "CLEAR") == 0) { estopLatched = false; Serial.println("OK CLEAR"); }
        else {
          char dir; int spd; unsigned long ms;
          if (sscanf(lineBuffer, "MOVE %c %d %lu", &dir, &spd, &ms) == 3) beginMove(dir, spd, ms);
          else Serial.println("ERR COMMAND");
        }
      }
      lineLength = 0;
    } else if (lineLength < sizeof(lineBuffer) - 1 && c != '\r') {
      lineBuffer[lineLength++] = c;
    }
  }
  if (moving && (long)(millis() - stopAt) >= 0) stopMotors();
}
```

#### 6.2 Teleoperation & Motor Dispatch API (`robot_routes.py`)
```python
@router.post("/api/robot/command")
def command(cmd: DriveCommand):
    if _state["estop"]:
        raise HTTPException(status_code=409, detail="Emergency stop active. Clear first.")
    
    wire_command = "STOP" if cmd.command == "S" else f"MOVE {cmd.command} {cmd.speed} {cmd.duration_ms}"
    ok, reply = arduino_serial.request(wire_command)
    if not ok:
        raise HTTPException(status_code=503, detail=reply)
    
    _state["commands"] += 1
    events.log("info", f"Drive {cmd.command} at {cmd.speed} PWM for {cmd.duration_ms}ms.")
    return {"status": "ok", "command": cmd.command}
```

#### 6.3 Parking Geometric Classification Logic (`parking_geometry.py`)
```python
def classify_vehicle(vehicle_poly_cm, vehicle_angle_deg, slots):
    v_poly = Polygon(vehicle_poly_cm)
    if not v_poly.is_valid or v_poly.area <= 0:
        return SlotResult(vehicle_id="unknown", violation=ViolationType.OUTSIDE_SLOT, confidence=0.0)
    
    best_slot = None
    best_intersection_area = 0.0
    for slot in slots:
        s_poly = Polygon(slot.polygon)
        inter = v_poly.intersection(s_poly).area
        if inter > best_intersection_area:
            best_intersection_area = inter
            best_slot = slot
            
    if best_slot is None:
        return SlotResult(slot_id=None, violation=ViolationType.OUTSIDE_SLOT, inside_fraction=0.0)
    
    fraction_inside = best_intersection_area / v_poly.area
    if best_slot.restricted and fraction_inside > 0.2:
        return SlotResult(slot_id=best_slot.slot_id, violation=ViolationType.NO_PARKING_ZONE)
    if fraction_inside < 0.60:
        return SlotResult(slot_id=best_slot.slot_id, violation=ViolationType.STRADDLING)
        
    angle_error = abs((vehicle_angle_deg - best_slot.angle_deg + 180) % 180 - 90)
    if angle_error > 35.0:
        return SlotResult(slot_id=best_slot.slot_id, violation=ViolationType.WRONG_ORIENTATION)
        
    return SlotResult(slot_id=best_slot.slot_id, violation=ViolationType.LEGAL, inside_fraction=fraction_inside)
```

---

### 7. Project Demonstration Video

- **Video Demonstration URL:** `[Insert Google Drive Link Here - e.g., https://drive.google.com/file/d/xxxxxx/view?usp=sharing]`
- **Share Permission:** Anyone with the link (Viewer / Editor enabled as per syllabus guidelines).
- **QR Code for Instant Video Access:**

```
+-----------------------------------------------------------+
|                                                           |
|                     [ INSERT QR CODE ]                    |
|             Generate via https://www.qr-code-generator.com|
|             pointing to the Google Drive Video URL        |
|                                                           |
+-----------------------------------------------------------+
Figure 4: QR Code Linking Directly to Project Demonstration Video
```

---

### 8. Conclusion

#### 8.1 Summary of Completed Work
The **ParkSensei** embedded smart parking enforcement prototype was successfully engineered and verified. The system demonstrates a reliable master-slave distributed computing architecture uniting a Raspberry Pi 5 with an Arduino Uno microcontroller. Through teleoperated skid-steer navigation, real-time planar homography vision analysis, offline license plate extraction via RapidOCR, and hardware ESC/POS thermal printing, the vehicle can systematically inspect parking lots, identify multiple categories of parking violations, and physically dispense citation tickets without relying on cloud infrastructure.

#### 8.2 Key Results and Observations
1. **Low-Latency Teleoperation & Safety Watchdog:** The 115200-baud newline ASCII protocol successfully clamped all motor leases between 100 ms and 500 ms, completely eliminating runaway conditions while maintaining smooth 4WD skid-steer responsiveness.
2. **Robust Geometric Coordinate Mapping:** By calculating the inverse homography transformation matrix $\mathbf{H}^{-1}$, 2D camera image coordinates were mapped accurately into physical centimeter-space coordinates, enabling detection of boundary straddling ($<60\%$ inside slot) and angular misalignments ($>35^\circ$ error).
3. **On-Device Edge Computing:** Both the FastAPI vision pipeline and the RapidOCR plate recognition models run fully on-device on the Pi 5's ARM processor, achieving zero-dependency offline operation.
4. **Physical Citation Verification:** The direct-thermal 58 mm printer produced clear, high-contrast 384 px citation receipts containing full diagnostic metadata, proving that physical enforcement can be integrated into compact embedded robotic platforms.
