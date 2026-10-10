# Offline Raspberry Pi hotspot

The Pi can provide its own local Wi-Fi network, so the demo does not need a
router, mobile hotspot, Ethernet, or internet connection. The Pi still needs
power; keep the camera and Arduino connected to it.

This setup script targets Raspberry Pi OS Bookworm using NetworkManager. Run it
once on the Pi from the repository directory:

```bash
sudo bash deploy/configure_pi_hotspot.sh
```

Enter a Wi-Fi password when prompted. The script creates a secured `PrintSensei`
network and gives the Pi the address `10.42.0.1`. It is configured to start at
boot. Connect your phone or laptop to `PrintSensei` and open
`http://10.42.0.1:8000/docs` to check the backend.

## Open the project UI offline

The Vercel page needs internet. For an offline demo, build the frontend on the
Pi before demo day. The backend serves `frontend/dist` at `/` when that build is
present. Run these commands once while the Pi has internet access, or after
transferring the frontend dependencies/build to it:

```bash
cd ~/Robotics_new/frontend
npm ci
VITE_API_URL= npm run build
sudo systemctl restart printsensei-robot
```

Keep `VITE_API_URL` empty when building so browser API calls go to the Pi using
the same origin. If the Pi's `.env` sets `API_KEY`, also provide that same value
as `VITE_API_KEY` during the build. Then connect to the Pi hotspot and open
`http://10.42.0.1:8000/`.

The hotspot provides local connectivity only. Phone/laptop clients connected to
it can reach the Pi, but cannot reach the internet through it.

## Check status or turn it off

```bash
nmcli connection show --active
sudo nmcli connection down printsensei-hotspot
sudo nmcli connection up printsensei-hotspot
```
