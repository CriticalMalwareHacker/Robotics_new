# PrintSensei Project Context and Handoff

This is a working handoff for another Codex account or developer. Read it with `README.md`, `deploy/ARDUINO_SERIAL.md`, and the current source. Code, the Pi's private `.env`, and fresh Pi output take precedence if this note becomes stale.

## Project and locations

PrintSensei combines a FastAPI backend/dashboard, a 58 mm thermal printer, parking/vehicle monitoring, and an Arduino-driven robot.

- Windows workspace: `C:\Users\tanay\OneDrive\Documents\Roboticsnew`
- Pi clone: `/home/ps/Robotics_new`
- Pi systemd service: `printsensei-robot`
- Observed service executable: `/home/ps/Robotics_new/venv/bin/uvicorn`, running as user `ps`.
- The checked-in unit template may show older `/home/pi/...` paths; the Pi's actual service configuration is authoritative.

## Hardware: drive and serial link

- Raspberry Pi 5 runs the backend and commands the robot.
- Arduino Uno connects to Pi over USB serial at 115200 baud.
- Uno has an Adafruit Motor Shield V1 (`AFMotor.h`) and four DC motors.
- Sketch: `arduino/park_sensei_serial/park_sensei_serial.ino`; M1+M3 are left, M2+M4 are right.
- Motor supply powers the shield/motors separately. Do not power motors from USB.
- PWM is currently forced to 255 because loaded motors did not start reliably at lower PWM.

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

## Hardware: obstacle sensors on Pi 5

Both sensors are connected to the Pi; Arduino remains the motor controller.

| Sensor pin | Pi connection |
| --- | --- |
| HC-SR04 VCC | 5 V, physical pin 2 |
| HC-SR04 GND | GND, physical pin 14 |
| HC-SR04 TRIG | BCM GPIO5, physical pin 29 |
| HC-SR04 ECHO | BCM GPIO6, physical pin 31, through a voltage divider |
| HW-201 IR VCC | 3.3 V, physical pin 1 |
| HW-201 IR GND | GND, physical pin 6 |
| HW-201 IR OUT | BCM GPIO22, physical pin 15 |

Do not connect HC-SR04's 5 V ECHO directly to a Pi GPIO. The documented divider is 1 kΩ from ECHO to GPIO6 and 2 kΩ from the GPIO6 junction to GND. IR is read active-low. The user confirmed IR indicator/detection and accurate changing ultrasonic distance readings.

GPIO23/24 were previously busy; `gpioinfo` showed GPIO24 held as output with consumer `dc`. Stopping the service did not immediately release that pin. GPIO5/6 were later found available and used for the ultrasonic sensor. Current defaults in `app/api/robot_routes.py`: IR GPIO22, ultrasonic trigger GPIO5, echo GPIO6. Pi `.env` can override via `ROBOT_IR_GPIO`, `ROBOT_ULTRASONIC_TRIGGER_GPIO`, `ROBOT_ULTRASONIC_ECHO_GPIO`.

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

The working route was to connect Pi to the saved NetworkManager profile `Airtel_8994`; `git pull` then succeeded. The user confirmed the pull and wanted the project hotspot back. To automate this without getting locked out of SSH, use the fail-safe `update.sh` script, or run:

```bash
# Automated 1-command updater with safety trap that always restores hotspot:
./update.sh
```

Or manually:

```bash
sudo nmcli connection down printsensei-hotspot
sudo nmcli connection up "Airtel_8994"
git pull origin robotics
sudo systemctl restart printsensei-robot
sudo nmcli connection down "Airtel_8994"
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

## Thermal receipt layout

`backend/services/parking/ticket.py` builds a Pillow RGB image at 384 px wide. `app/api/hud_routes.py` uses it for test/violation tickets, saves a PNG, then prints through `app/services/printer.py`; the image is also previewed in the dashboard.

The latest local edit redesigns the receipt with a clearer heading, ticket/date details, a boxed prominent plate, vehicle/bay rows, emphasized observed violation, and prototype/not-a-fine disclaimer. Long fields wrap within the print margins. Width remains 384 px.

At last inspection, `git status --short` showed `backend/services/parking/ticket.py` modified. The redesign was not committed/pushed and has not been verified by preview or physical print. Once deployed, restart the backend and use test-print to inspect the image and paper output.

## Git and deployment workflow

User edits the Windows workspace, pushes to GitHub, then pulls on Pi in `~/Robotics_new`. Pi internet may require switching temporarily from PrintSensei AP to `Pranshu`; restore the AP after pulling. Never take down the only network path carrying SSH.

Typical Pi deploy after user pushes:

```bash
cd ~/Robotics_new
git pull
sudo systemctl restart printsensei-robot
sudo systemctl status printsensei-robot --no-pager
```

On Windows, inspect `git status --short` before staging. Do not commit `.env`, Wi-Fi secrets, generated images, or logs. `.env` should remain private and gitignored.

## Pending actions and working style

1. Confirm GPIO service restart and retry Start Auto. If it still fails, request exact UI error and recent `journalctl` output instead of guessing.
2. Check sensor stop behavior with wheels raised before a floor run.
3. Commit/push receipt edit when ready; pull it on Pi, restart service, and inspect a test print.
4. Preserve short motor leases and stop behavior when changing patrol code.
5. User prefers practical, direct command-by-command help and commonly runs commands over SSH.
6. Network state, routes, sensor pin ownership, and Pi service config can change; request fresh diagnostics when current state matters.
