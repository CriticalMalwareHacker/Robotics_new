# HOIN Bluetooth ESC/POS printer

The ticket endpoint creates the existing 384-dot ESC/POS raster ticket. For a
Bluetooth HOIN model that accepts ESC/POS over Classic Bluetooth, the Pi can
send the raster directly over RFCOMM; it does not need USB or a printer cloud.

## Pair the printer once on the Pi

Turn on the printer and put it in Bluetooth pairing mode. On the Pi:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
```

Copy the printer MAC address shown by the scan, then enter:

```text
scan off
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
quit
```

If it asks for a PIN, use the one in the printer's manual/label. Pairing is
saved by Raspberry Pi OS; the phone/laptop viewing the HUD does not need to pair
with the printer.

## Configure the backend

Edit `~/Robotics_new/.env` on the Pi and add the printer's actual Bluetooth MAC:

```dotenv
PRINTER_TRANSPORT=bluetooth
PRINTER_BLUETOOTH_ADDRESS=AA:BB:CC:DD:EE:FF
PRINTER_BLUETOOTH_CHANNEL=1
```

Restart and inspect the backend:

```bash
sudo systemctl restart printsensei-robot
sudo systemctl status printsensei-robot
```

The HUD will list every detected violation. Plate OCR is not implemented, so
check the printed mat/car plate and enter it in that car's row. **Print ticket**
then rechecks that the car is still visible and violating before sending the
ticket. If a ticket cannot reach the printer, its image is saved in ticket
history and the HUD shows the print failure.

The Bluetooth implementation expects Classic Bluetooth RFCOMM and an ESC/POS
compatible model. HOIN sells multiple models, so verify your specific printer
supports ESC/POS over Bluetooth; BLE-only models need their vendor protocol.
