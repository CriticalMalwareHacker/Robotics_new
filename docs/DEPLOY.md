# DEPLOY.md — Pi hosts backend, frontend runs anywhere

## 1. Pi first boot (backend live on every boot)

```bash
# on the Pi
cd ~/AI-Robotics_PrintSensei
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env  # then edit: set API_KEY=<random token> (see docs/REMOTE_ARCHITECTURE.md)

# serial + printer groups (re-login after)
sudo usermod -aG dialout,lp $USER

# install + enable the boot service (edit paths/user inside first if yours differ)
sudo cp deploy/printsensei-robot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now printsensei-robot
systemctl status printsensei-robot  # expect active (running)
curl http://127.0.0.1:8000/api/parking/status  # expect {"monitor":"stopped",...}
```

Boot behavior is safe by design: the app starts in IDLE (monitor `stopped`,
motors untouched). It waits for START from the HUD. `AUTOSTART` is not needed.

## 2. Reach it from outside (pick one, see docs/REMOTE_ARCHITECTURE.md)

Recommended — Cloudflare Tunnel (https URL, no router changes):

```bash
cloudflared tunnel --url http://localhost:8000
# -> https://<name>.trycloudflare.com  (use as VITE_API_URL)
```

Same-Wi-Fi testing needs nothing: `VITE_API_URL=http://<pi-lan-ip>:8000`.

## 3. Run the frontend on the side (your laptop/phone)

Local dev:

```bash
cd frontend && cp .env.example .env  # set VITE_API_URL to the Pi
npm install && npm run dev  # open the printed URL, tap Parking tile
```

Deployed (Vercel/Netlify/etc.): set `VITE_API_URL` + `VITE_API_KEY` in the
host's env vars, deploy `frontend/` (build command `npm run build`,
output `dist/`). Open from your phone (mobile data works with the tunnel URL).

## 4. Smoke test the whole chain

1. Backend: `curl -H "Authorization: Bearer <API_KEY>" <pi-url>/api/parking/status`
2. HUD: open frontend → Parking tile → START MONITOR → move a paper car badly → red violation pill + banner within ~1 s.
3. Reboot the Pi: backend returns without SSH; HUD reconnects on its own (polling).

## 5. Camera on the Pi

The Hikvision is picked as the first `/dev/video*` device. If several cameras
are attached, set `CAMERA_INDEX=<n>` in the Pi's `.env` and restart the service.

For Uno manual-drive setup, upload the serial sketch and configure
`ROBOT_SERIAL_PORT`/`ROBOT_MODE` as described in
[`ARDUINO_SERIAL.md`](ARDUINO_SERIAL.md). Keep `ROBOT_MODE=mock` until the
serial sketch is installed and the Uno is connected.
