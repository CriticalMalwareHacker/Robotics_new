# PrintSensei / ParkSensei — project handoff

Prepared 14 October 2026 from the project chat. This note is a working handoff for the next person helping Tanay. Treat uncertain hardware claims as unverified and confirm them on the robot.

## Project goal

Build a self-hosted parking-monitoring robot/demo. A Raspberry Pi hosts the backend and HUD, a camera watches a paper parking mat, OpenCV identifies vehicles and parking-space violations, OCR reads number plates, the Arduino drives the car through an Adafruit Motor Shield, and a HOIN thermal printer can print a violation ticket. The project should work locally without internet during a demo.

## Hardware and current roles

- Raspberry Pi 5, 8 GB: local backend, camera processing, HUD hosting, and Wi-Fi hotspot.
- Arduino Uno with an AFMotor-compatible Adafruit Motor Shield V1: wheel control over USB serial.
- Camera: connected to the Pi; HUD has shown camera online and live frames in earlier tests.
- Ultrasonic sensor: intended as a front-facing HC-SR04. The exact sensor model and working wiring are not yet confirmed.
- HOIN ESC/POS thermal printer: Bluetooth address `66:32:D4:A7:0B:96`.

## What has been verified

- The Pi backend ran as the `printsensei-robot` systemd service and listened on port 8000.
- The Pi hotspot setup in `deploy/configure_pi_hotspot.sh` is intended to create a local `PrintSensei` Wi-Fi network at `10.42.0.1`. The intended local UI is `http://10.42.0.1:8000/`; API docs are at `http://10.42.0.1:8000/docs`.
- The backend was reachable over the local network. Pi logs showed `/api/hud/state` returning `200 OK`.
- The Arduino Uno appeared as `/dev/serial/by-id/usb-Arduino__www.arduino.cc__Arduino_Uno_12254501101139321640-if00` on the Pi, and a backend `MOVE F` command moved the car forward. Manual controls use the serial firmware described below.
- The HOIN printer was found by Pi Bluetooth scanning with a strong signal. Its Serial Port service was discovered at RFCOMM channel **2**.
- Pi OCR models for RapidOCR were present in the virtual environment. Logs included “text detection result is empty” for some frames; OCR accuracy/plate reading is not yet confirmed.
- A production frontend build succeeded on the Windows development machine after extending print request timeouts.

## Current Arduino firmware

File: `arduino/park_sensei_serial/park_sensei_serial.ino`

The sketch uses `AFMotor.h`, motor channels 1 and 2, and newline-delimited serial commands at 115200 baud:

```text
PING                 -> PONG
MOVE F|B|L|R pwm ms  -> OK MOVE (lease limited to 500 ms)
STOP                 -> OK STOP
ESTOP                -> OK ESTOP (latched until CLEAR)
CLEAR                -> OK CLEAR
STATUS               -> STATUS IDLE|MOVING|ESTOP
```

Current four-motor mapping: M1+M3 are the left side; M2+M4 are the right side. Forward/back drives all four motors; left/right releases the inside pair and drives the outside pair forward. Manual drive protocol remains unchanged. The sensor addition is configured for TRIG on A0 and ECHO on A1; if the motors are idle and an object is measured within 18 cm twice, it reverses all four motors at PWM 120 for 250 ms. It rearms after readings at least 26 cm away or no echo. It intentionally does not interrupt manual movement. On startup the sketch releases all motors.

The ultrasonic wiring notes are in `deploy/ARDUINO_SERIAL.md`. For a standard 4-pin HC-SR04:

| HC-SR04 | Uno / shield analog header |
| --- | --- |
| VCC | 5V |
| GND | GND |
| TRIG | A0 |
| ECHO | A1 |

Use the pin labels printed on the sensor and shield, not left/right orientation. Connect to the Uno, never the Pi GPIO. Turn power off before rewiring.

### Ultrasonic sensor unresolved issue

- A standalone HC-SR04 test sketch at 9600 baud printed only `No echo`.
- Tanay reports wiring VCC to +5V, GND to GND, ECHO to A1, TRIG to A0, and has no multimeter.
- The supplied photos showed the motor shield and jumper leads but did not clearly show the ultrasonic module’s model/pin labels. The model is therefore still unconfirmed; the HC-SR04 sketch only applies if it is a compatible four-pin sensor.
- No working distance reading or automatic reverse has been verified. `pulseIn()` returning no pulse is treated as distance 0/clear, so the sensor will not trigger when it has no echo.
- Next debugging step: get a clear photo of the sensor front/back and its pin labels/model; confirm all four leads; use the standalone distance sketch with a flat target around 20 cm away. If testing with that sketch, it replaces the robot firmware; afterward re-upload `park_sensei_serial.ino` at 115200 baud. The standalone tester uses 9600 baud.
- If the robot is left powered before sensor testing, disconnect motor power to prevent any automatic movement if the sensor begins detecting.

## Printer status and next step

The Pi discovered `BlueTooth Printer` at `66:32:D4:A7:0B:96`. `bluetoothctl pair` and generic `connect` attempts failed, but this command found the printer’s SPP service:

```text
sudo sdptool search --bdaddr 66:32:D4:A7:0B:96 SP
Service Name: HS_SPP
UUID: Serial Port (0x1101)
RFCOMM Channel: 2
```

The printer code in `app/services/printer.py` uses a raw RFCOMM socket and reads `PRINTER_BLUETOOTH_CHANNEL` (defaults to 1). Tanay was instructed to set these in the Pi’s gitignored `~/Robotics_new/.env`:

```dotenv
PRINTER_TRANSPORT=bluetooth
PRINTER_BLUETOOTH_ADDRESS=66:32:D4:A7:0B:96
PRINTER_BLUETOOTH_CHANNEL=2
```

The backend was restarted afterward. The captured log showed systemd killing the previous Uvicorn workers after a stop timeout, then the new Uvicorn process starting successfully and serving HUD requests. It did **not** show a print-test POST, so physical printing remains unverified.

Next: verify only the three printer settings (do not paste the whole `.env` because it may contain secrets), then watch logs and click **Print test once**:

```bash
grep -E '^PRINTER_(TRANSPORT|BLUETOOTH_ADDRESS|BLUETOOTH_CHANNEL)=' ~/Robotics_new/.env
sudo journalctl -fu printsensei-robot
```

If print fails, capture the HUD error and log lines for the print endpoint. The HUD’s **Printer · Ok** status only checks that Bluetooth configuration/address exists; it does not prove a successful print.

## Frontend / print timeout

In `frontend/src/hud/api.js`, print requests have a 30-second timeout because the Bluetooth connection can take longer than ordinary HUD requests. The frontend production build succeeded locally. This timeout only prevents the browser from aborting too early; it does not fix Bluetooth connectivity or guarantee printing. A browser abort also does not necessarily cancel a print already started by the backend, so check ticket history/printer before retrying.

The Pi serves `frontend/dist` if it exists. For the offline frontend, the deployment notes use:

```bash
cd ~/Robotics_new/frontend
npm ci
VITE_API_URL= npm run build
sudo systemctl restart printsensei-robot
```

If the backend `.env` uses `API_KEY`, the frontend build may also need the same value supplied as `VITE_API_KEY`. Keep secrets out of this handoff and out of Git.

## Camera, parking map, and vision context

- Tanay provided a photo of a hand-drawn three-bay parking mat and asked for boxes/lines to be mapped. A later camera photo showed a different fixed camera angle, a vehicle in one bay, and another paper car parked between lines.
- The HUD has displayed the live camera and parking-space overlays in prior sessions. Camera angle and parking boundaries need validation against the current camera pose before claiming precise violation detection.
- OpenCV parking detection, plate reading, and ticket workflow are the desired end goal, but stable current accuracy is unverified. OCR logs showed empty detections at least for some frames.
- The `Start auto` action was documented as starting the vision monitor only; autonomous camera-guided driving/navigation has not been demonstrated. Do not describe the robot as fully autonomous yet.

## Git / deployment caution

Tanay owns `CriticalMalwareHacker/Robotics_new` and does not want changes pushed to another repository. Earlier Windows `git push` commands failed because `origin` appeared configured as the bare string `CriticalMalwareHacker/Robotics_new` rather than a valid remote URL. Check `git remote -v` before pushing and ensure it points to Tanay’s repository. Do not use `git push --force` to fix a malformed remote. The Pi repo has previously been cloned under `~/Robotics_new`.

## Suggested handoff order

1. Verify the Pi service and local hotspot/UI are still up.
2. Verify the printer `.env` values and perform one supervised print test on RFCOMM channel 2.
3. Identify the ultrasonic module by its printed model and test it independently until Serial Monitor shows changing distances. Only then rely on the auto-reverse behavior.
4. Re-upload the serial robot sketch after any standalone sensor test and retest manual movement.
5. Validate camera calibration/parking-space overlays and OCR on current live footage before treating violation/ticket automation as complete.

## Secrets and safety

- Local environment audit on 14 October 2026: the workspace contains `frontend/.env` with `VITE_API_URL` and `VITE_API_KEY`; `VITE_API_KEY` is empty. The tracked `.env.example` files contain provider-key variable names, but those values are empty too. No secret value was printed during this check. The Pi's separate `~/Robotics_new/.env` is not in this Windows workspace and was not inspected; treat it as potentially sensitive.
- `frontend/.env` and root `.env` are ignored by `.gitignore`; only `.env.example` templates are tracked. Keep real environment files out of Git and redact Wi-Fi passwords, API keys, and tokens from screenshots. Vite `VITE_*` values are compiled into client code, so never put a private provider key there.
- First test motor behavior with wheels lifted and clear space behind the car. The timed software stop is not a physical emergency stop.
- Power down before changing sensor wiring. The Uno’s HC-SR04 Echo is for the Uno input; never connect it to a Pi GPIO.
