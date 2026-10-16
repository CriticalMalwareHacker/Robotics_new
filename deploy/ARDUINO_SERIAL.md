# Uno serial control on the Raspberry Pi

The checked-in Arduino sketch is separate from the user's original looping
motor test. It waits for short commands from the FastAPI backend, so booting
the Uno does not start the motors. It supports four motors on an Adafruit
Motor Shield V1: channels M1 and M3 are configured as the left side; M2 and M4
are the right side.

## 1. Upload the serial sketch once

Open `arduino/park_sensei_serial/park_sensei_serial.ino` in Arduino IDE on a
computer, select **Arduino Uno**, and upload it. Install the V1 **Adafruit
Motor Shield library** that provides `AFMotor.h` first. This sketch does not
use V2's I2C shield detection. The Uno keeps this firmware after it is
unplugged; Arduino IDE is not needed on the Pi to run it.

The serial protocol is 115200 baud, newline-delimited ASCII:

```text
PING                         -> PONG
MOVE F 120 200               -> OK MOVE
MOVE B 120 200               -> OK MOVE
MOVE L 120 200               -> OK MOVE (left backward; right forward)
MOVE R 120 200               -> OK MOVE (left forward; right backward)
STOP                         -> OK STOP
ESTOP                        -> OK ESTOP
CLEAR                        -> OK CLEAR
STATUS                       -> STATUS IDLE | STATUS MOVING | STATUS ESTOP
```

The firmware accepts leases from 100 to 500 ms and releases all four motor
channels when a lease expires. Auto mode renews a 220 ms lease; if Pi commands
stop arriving, the Arduino therefore releases the motors within that lease.
`L` and `R` counter-rotate the left and
right sides, so all four motors run during a turn. Nonzero manual speeds are
currently raised to PWM 255 because the V1 diagnostic confirmed all four
loaded motors start at that setting. Auto mode also uses full PWM by default;
keep the robot on a clear tabletop and supervise it.
If your chassis wires different shield channels to each side, adjust the
left/right channel mapping in the sketch. The HUD renews a short lease while a
manual-drive control is held and sends `STOP` on release. This software stop
is not a substitute for a physical motor-power switch or hardware emergency
stop.

## 2. Connect and identify the Uno on the Pi

Connect the Uno to a Pi USB port. Do not power the motors from Pi USB; keep the
motor supply connected to the shield as already tested. Find the stable port:

```bash
ls -l /dev/serial/by-id/
```

If that directory is empty, inspect `ls -l /dev/ttyACM* /dev/ttyUSB*`.
The Uno resets when a serial client opens USB, so the backend waits two seconds
and checks for a `PING`/`PONG` handshake before reporting the link as online.

## 3. Configure the backend service

Install the Python dependencies in the project's virtual environment (this
includes `pyserial` and GPIO Zero), and ensure the same environment can import
`lgpio` for Raspberry Pi 5 GPIO access. Check with
`<venv>/bin/python -c "import gpiozero, lgpio"`. Then set these values in the
Pi's gitignored `.env`:

```dotenv
ROBOT_MODE=real
ROBOT_SERIAL_PORT=/dev/serial/by-id/<the-exact-device-name>
ROBOT_SERIAL_BAUD=115200
```

Grant the service account access to the Uno's serial group. The checked-in
systemd unit runs as `pi`:

```bash
sudo usermod -aG dialout pi
sudo systemctl restart printsensei-robot
sudo systemctl status printsensei-robot
```

After adding a group, reboot if the service does not inherit the new group.
The HUD's **Manual drive** controls send `F`, `B`, `L`, `R`, and `S` through
the backend. **Start auto** now runs a supervised tabletop patrol in real mode.

## 4. Obstacle sensors

With power disconnected, wire both obstacle sensors to the Raspberry Pi. Keep
the Uno connected to the Pi by USB for motor control.

| HC-SR04 pin | Raspberry Pi 5 |
| --- | --- |
| VCC | 5V (physical pin 2) |
| GND | GND (physical pin 14) |
| TRIG | GPIO5 (physical pin 29) |
| ECHO | GPIO6 (physical pin 31), through a voltage divider |
| HW-201 IR module VCC | Pi 3.3V (physical pin 1) |
| HW-201 IR module GND | Pi GND (physical pin 6) |
| HW-201 IR module OUT | Pi GPIO22 (physical pin 15) |

Do not connect HC-SR04 ECHO directly to a Pi GPIO: the common HC-SR04 emits a
5 V ECHO signal, while Pi GPIO is 3.3 V. Use a 1 kΩ resistor from ECHO to the
GPIO6 junction, and a 2 kΩ resistor from that junction to GND:

```text
HC-SR04 ECHO ---- 1 kΩ ----+---- Pi GPIO6 (physical pin 31)
                           |
                          2 kΩ
                           |
                          GND
```

The Pi reads HC-SR04 distance and the active-low HW-201 output with GPIO Zero
and uses both in autonomous obstacle checks. The Arduino continues to receive
motor commands over USB serial. Power the HW-201 from 3.3 V so its OUT signal
stays safe for the Pi. The module is a short-range digital proximity switch;
its potentiometer adjusts the detection threshold. GPIO assignments can be
changed with `ROBOT_IR_GPIO`, `ROBOT_ULTRASONIC_TRIGGER_GPIO`, and
`ROBOT_ULTRASONIC_ECHO_GPIO`.

## 5. Supervised tabletop patrol

With `ROBOT_MODE=real`, Start auto sends short forward leases and checks both
Pi-connected obstacle sensors. On an obstacle it stops, alternates a timed
left/right pivot, and checks again. After four failed pivots it stops and
reports a blocked state. A newly debounced parking violation also stops the
motors and enters review. The HUD requires **Confirm bad parking**, then
**Print ticket**, then **Go ahead** before patrol resumes. Stop and E-stop
remain available.

Optional Pi `.env` tuning:

```dotenv
ROBOT_AUTO_PWM=255
ROBOT_AUTO_LEASE_MS=220
ROBOT_AUTO_TURN_MS=350
ROBOT_OBSTACLE_CM=18
```

The firmware currently raises every nonzero speed to 255 because lower PWM
did not reliably start the loaded motors. Timed pivots are not calibrated for
distance or angle: there are no wheel encoders, side-facing range sensors, or
global position estimate. This is supervised demo behavior, not reliable
autonomous parking or navigation. Test with the wheels raised, then in a clear
area while supervising the robot and keeping a hand on the power switch. The
camera calibration maps the tabletop in its calibrated view; moving the
robot/camera relative to the paper lot can invalidate that mapping, so verify
the overlay before relying on parking classification.
