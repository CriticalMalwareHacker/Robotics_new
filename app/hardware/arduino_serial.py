"""USB-serial link for the Uno + Adafruit Motor Shield robot controller.

The Arduino owns motor timing and stops leased movements automatically. The
API sends short, line-based commands and treats a missing reply as offline.
"""

from __future__ import annotations

import glob
import os
import threading
import time


class ArduinoSerialLink:
    def __init__(self) -> None:
        self._serial = None
        self._port: str | None = None
        self._last_error = "Arduino serial link has not connected."
        self._last_attempt = 0.0
        self._lock = threading.RLock()

    @staticmethod
    def _ports() -> list[str]:
        configured = os.getenv("ROBOT_SERIAL_PORT", "").strip()
        if configured:
            return [configured]

        # Prefer stable Linux device names; retain common fallbacks for a Pi
        # whose Uno enumerates as ttyACM0/ttyUSB0.
        found = sorted(glob.glob("/dev/serial/by-id/*"))
        return found + ["/dev/ttyACM0", "/dev/ttyUSB0"]

    def _close_locked(self) -> None:
        ser, self._serial = self._serial, None
        self._port = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    def _connect_locked(self) -> bool:
        now = time.monotonic()
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return True
        if now - self._last_attempt < 1.5:
            return False
        self._last_attempt = now

        try:
            import serial
        except ImportError:
            self._last_error = "pyserial is missing; install the project requirements."
            return False

        baud = int(os.getenv("ROBOT_SERIAL_BAUD", "115200"))
        for port in self._ports():
            try:
                ser = serial.Serial(port, baudrate=baud, timeout=0.12,
                                    write_timeout=0.25)
                # Opening an Uno's USB serial port resets it. Let its bootloader
                # finish, discard startup text, then require a PONG handshake.
                time.sleep(2.0)
                ser.reset_input_buffer()
                ser.write(b"PING\n")
                ser.flush()
                reply = ser.readline().decode("ascii", "replace").strip()
                if reply != "PONG":
                    ser.close()
                    self._last_error = f"No PONG handshake from Arduino on {port}."
                    continue
                self._serial = ser
                self._port = port
                self._last_error = ""
                return True
            except Exception as exc:
                self._last_error = f"Could not open/handshake with {port}: {exc}"
        return False

    def connected(self) -> bool:
        with self._lock:
            return self._connect_locked()

    @property
    def port(self) -> str | None:
        with self._lock:
            return self._port

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def request(self, command: str) -> tuple[bool, str]:
        with self._lock:
            if not self._connect_locked() or self._serial is None:
                return False, self._last_error or "Arduino is offline."
            try:
                self._serial.reset_input_buffer()
                self._serial.write((command.strip() + "\n").encode("ascii"))
                self._serial.flush()
                reply = self._serial.readline().decode("ascii", "replace").strip()
                if reply.startswith("OK") or reply in {"PONG", "STATUS IDLE", "STATUS ESTOP"}:
                    return True, reply
                self._last_error = reply or "Arduino did not reply before timeout."
                self._close_locked()
                return False, self._last_error
            except Exception as exc:
                self._last_error = f"Arduino serial request failed: {exc}"
                self._close_locked()
                return False, self._last_error

    def close(self) -> None:
        with self._lock:
            self._close_locked()


arduino_serial = ArduinoSerialLink()
