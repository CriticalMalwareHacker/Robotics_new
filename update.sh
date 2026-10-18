#!/usr/bin/env bash
# ParkSensei: One-command Pi updater with safe Wi-Fi hopping
# Switches to internet Wi-Fi, pulls latest code from GitHub, restarts the service,
# and ALWAYS restores the ParkSensei hotspot on exit (even on failure or Ctrl+C).

set -eo pipefail

HOTSPOT_CONNECTION="printsensei-hotspot"
INTERNET_SSID="${1:-Airtel_Zerotouch_5G}"
INTERNET_PASS="${2:-Airtel@123}"
SERVICE_NAME="printsensei-robot"
PROJECT_DIR="${HOME}/Robotics_new"

echo "=========================================="
echo " ParkSensei One-Command GitHub Updater"
echo "=========================================="

restore_hotspot() {
    echo ""
    echo "[*] Restoring project hotspot (${HOTSPOT_CONNECTION})..."
    sudo nmcli connection down "${INTERNET_SSID}" >/dev/null 2>&1 || true
    sudo nmcli connection up "${HOTSPOT_CONNECTION}" || {
        echo "[!] Warning: Could not bring up ${HOTSPOT_CONNECTION} automatically."
        echo "    Try running: sudo nmcli connection up ${HOTSPOT_CONNECTION}"
    }
    echo "[✓] Hotspot restored! Pi is back online at 10.42.0.1"
}

# Ensure the hotspot is ALWAYS restored no matter what happens (error, exit, or SIGINT)
trap restore_hotspot EXIT

echo "[1/4] Switching Wi-Fi: Hotspot OFF -> '${INTERNET_SSID}' ON..."
sudo nmcli connection down "${HOTSPOT_CONNECTION}" || true

# If the Wi-Fi connection profile is not yet saved, connect with password; otherwise activate it
if sudo nmcli connection show "${INTERNET_SSID}" >/dev/null 2>&1; then
    echo "      Found existing profile for '${INTERNET_SSID}', activating..."
    sudo nmcli connection up "${INTERNET_SSID}" || sudo nmcli device wifi connect "${INTERNET_SSID}" password "${INTERNET_PASS}"
else
    echo "      Connecting to '${INTERNET_SSID}' with password..."
    sudo nmcli device wifi connect "${INTERNET_SSID}" password "${INTERNET_PASS}"
fi

echo "[2/4] Testing internet connectivity..."
CONNECTED=0
for i in {1..10}; do
    if ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        CONNECTED=1
        break
    fi
    echo "      Waiting for Wi-Fi route ($i/10)..."
    sleep 1
done

if [[ $CONNECTED -ne 1 ]]; then
    echo "[✗] Error: Could not reach the internet through '${INTERNET_SSID}'."
    exit 1
fi
echo "      Internet is reachable!"

echo "[3/4] Pulling latest changes from GitHub (robotics branch)..."
cd "${PROJECT_DIR}"
git pull origin robotics

if command -v npm >/dev/null 2>&1 && [[ -d "${PROJECT_DIR}/frontend" ]]; then
    echo "      Rebuilding frontend distribution..."
    (cd "${PROJECT_DIR}/frontend" && npm run build) || true
fi

echo "[4/4] Restarting ${SERVICE_NAME} service..."
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl --no-pager status "${SERVICE_NAME}" | head -n 12 || true

echo ""
echo "=========================================="
echo " Update complete! Changes are live."
echo "=========================================="
