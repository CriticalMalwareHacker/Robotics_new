# Remote architecture: Pi hosts backend, frontend deployed anywhere

Revised plan note: Arduino/motors are **deferred**. Order is now: test cases +
violation engine (done, this phase) → CV detector on real mat frames → HUD
dashboard → deploy frontend → ticket/plates → navigation/state machine → motors.

## 1. How it works (the whole trick in 6 lines)

1. The Pi runs the FastAPI backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
2. The React frontend is static files (`npm run build` → `dist/`). Host them anywhere
   (Vercel, Netlify, GitHub Pages, or the Pi itself).
3. The **browser** (your phone/laptop) calls the Pi **directly** over HTTP(S) —
   there is no server-side coupling. The only link between them is two values:
   `VITE_API_URL` (where is the Pi?) and `VITE_API_KEY` (prove you're allowed in).
4. You put those two values in the frontend host's **environment variables** and rebuild.
5. The Pi checks the key on every `/api/parking/*` call (`app/api/deps.py`).
   Existing PrintSensei routes stay open/unchanged for local use.
6. The HUD polls `GET /api/parking/status` every 500–1000 ms and draws the returned
   boxes/slots/violations over the live `<img>` — Iron-Man style, all client-side.

```text
[Vercel/Netlify: static React]  --VITE_API_URL + VITE_API_KEY (baked at build)-->
        |
        v  (your browser fetches JSON + JPEG straight from the Pi)
[Pi: uvicorn :8000] -- checks Authorization: Bearer <API_KEY> on /api/parking/*
  |-- vision / analyzer / printer / (later) serial to Arduino
```

## 2. Reaching the Pi from anywhere (pick ONE)

The browser must be able to open `VITE_API_URL`. On home Wi-Fi that's just
`http://<pi-ip>:8000`. From outside, pick one:

| Option | Setup | Best for |
|---|---|---|
| **A. Cloudflare Tunnel (recommended)** | `cloudflared tunnel --url http://localhost:8000` on Pi → you get `https://<name>.trycloudflare.com`. Free, encrypted, no router changes, works behind any NAT. For a stable name, create a free Cloudflare account once. | Demo day, phone on mobile data |
| B. Same Wi-Fi only | `VITE_API_URL=http://<pi-lan-ip>:8000`. Zero setup. | Home testing |
| C. Port forward (last resort) | Router forwards 8000 → Pi + dynamic DNS. Exposes the Pi to the internet; use a strong API key. | No other option |

Note: HTTPS pages (Vercel/Netlify) **cannot** call `http://` backends (mixed-content
block). So a publicly deployed frontend needs option A (https tunnel URL), not B.

## 3. Keys: generate, store, use (no secrets in git, ever)

On the Pi, generate and store (in the Pi's `.env`, which is gitignored):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# paste after API_KEY= in the Pi's .env, then restart uvicorn
```

On the frontend host, set environment variables and **rebuild**:

```text
VITE_API_URL=https://<your-tunnel-url>   # no trailing slash
VITE_API_KEY=<same token as the Pi>
```

Then `npm run build` (or your host auto-builds on push). Gotcha: Vite bakes
`VITE_*` values into the JS **at build time** — changing a variable without
rebuilding does nothing. `frontend/src/lib/api.js` sends the key as
`Authorization: Bearer <key>` (falls back to `X-Api-Key`); the Pi accepts
either. With `API_KEY` empty (laptop dev), auth is open and no header is sent.

## 4. Endpoints the HUD consumes

```text
POST /api/parking/analyze   {detections: [{vehicle_id, polygon[[x,y]..], angle_deg, confidence}]}
                            -> ParkingAnalysis (vehicle_detected, slot, parking_valid,
                               violation, confidence, plate, results[])
GET  /api/parking/status    -> {monitor, detector, slots_loaded, analyses_served, last_analysis}
GET  /api/camera/frame      -> live JPEG (already exists, reused)
GET  /api/parking/frame     -> annotated JPEG (lands with the detector, Phase 5)
```

Example analysis response (contract the HUD renders):

```json
{
  "vehicle_detected": true, "slot": "A3", "parking_valid": false,
  "violation": "OUTSIDE_SLOT", "confidence": 0.92, "plate": "MH01AB1234",
  "timestamp": "2026-10-01T12:00:00"
}
```

HUD loop (next phase, `RoboticsPanel.jsx`): poll `/status` @500–1000 ms →
`<img src={API_URL + '/api/camera/frame'}>` refreshed on interval → absolutely-
positioned SVG/div overlays from `last_analysis.results` (green LEGAL, red
violation + label). No App.jsx restructuring — one imported section.

## 5. Security notes

- API key is a shared secret over HTTPS (tunnel encrypts). Rotate by changing
  both sides + rebuild.
- CORS is open (`*`) — fine for a key-authenticated JSON API with no cookies.
- Never commit `.env`, tunnel URLs with tokens, or keys. `.env.example` documents
  names only.
- Printer/serial stay Pi-local; the network never touches `/dev/usb/lp0` except
  through validated Pydantic payloads.

## 6. Local-dev quick path (no tunnel, no key)

```bash
# terminal 1 (backend)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# terminal 2 (frontend) — vite proxies /api to :8000, or set VITE_API_URL
cd frontend && cp .env.example .env && npm run dev
```

## 7. Deploy checklist (when HUD lands)

- [ ] Pi: `API_KEY` set, uvicorn reachable via tunnel URL, `curl -H "Authorization: Bearer <k>" <tunnel>/api/parking/status` returns 200
- [ ] Host: `VITE_API_URL` + `VITE_API_KEY` set, production build done
- [ ] Phone (mobile data): dashboard loads, live frame moves, violations overlay
- [ ] `API_KEY` empty nowhere in production; `.env` never committed
