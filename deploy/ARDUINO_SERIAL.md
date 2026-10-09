# Uno serial control on the Raspberry Pi

The checked-in Arduino sketch is separate from the user's original looping
motor test. It waits for short commands from the FastAPI backend, so booting
the Uno does not start the motors.

## 1. Upload the serial sketch once

Open `arduino/park_sensei_serial/park_sensei_serial.ino` in Arduino IDE on a
computer, select **Arduino Uno**, and upload it. The AFMotor library used by
the existing motor test must be installed. The Uno keeps this firmware after
it is unplugged; Arduino IDE is not needed on the Pi to run it.

The serial protocol is 115200 baud, newline-delimited ASCII:

```text
PING                         -> PONG
MOVE F 120 200               -> OK MOVE
MOVE B 120 200               -> OK MOVE
MOVE L 120 200               -> OK MOVE
MOVE R 120 200               -> OK MOVE
STOP                         -> OK STOP
ESTOP                        -> OK ESTOP
CLEAR                        -> OK CLEAR
STATUS                       -> STATUS IDLE | STATUS MOVING | STATUS ESTOP
```

The firmware caps each movement lease at 500 ms and releases both motors when
that lease expires. The HUD renews a short lease while a manual-drive control
is held and sends `STOP` on release. This software stop is not a substitute for
a physical motor-power switch or hardware emergency stop.

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
includes `pyserial`), then set these values in the Pi's gitignored `.env`:

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
the backend. The current **Start auto** action only starts the vision monitor;
autonomous motor navigation is not implemented yet and is rejected in real
robot mode.

The ultrasonic sensor is not included in this first serial protocol. Add its
Arduino wiring/readings and a stop rule as a separate step after manual serial
driving works on the Pi.
