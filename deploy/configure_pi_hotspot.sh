#!/usr/bin/env bash
set -euo pipefail

# Configure a Raspberry Pi OS Bookworm (NetworkManager) Wi-Fi access point.
# The AP is local only; it does not require an internet connection.

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/configure_pi_hotspot.sh"
  exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
  echo "nmcli was not found. This setup expects Raspberry Pi OS Bookworm with NetworkManager."
  exit 1
fi

WIFI_IFACE="${WIFI_IFACE:-wlan0}"
HOTSPOT_SSID="${HOTSPOT_SSID:-PrintSensei}"
HOTSPOT_CONNECTION="printsensei-hotspot"
PI_HOTSPOT_IP="10.42.0.1/24"

if ! nmcli -t -f DEVICE device status | grep -Fxq "$WIFI_IFACE"; then
  echo "Wi-Fi interface '$WIFI_IFACE' was not found. Check: nmcli device status"
  exit 1
fi

read -r -s -p "Choose a Wi-Fi password (at least 8 characters): " HOTSPOT_PASSWORD
echo
if [[ ${#HOTSPOT_PASSWORD} -lt 8 ]]; then
  echo "The password must be at least 8 characters."
  exit 1
fi

# Set the regulatory country when raspi-config is available. This lets the Pi
# use legal Wi-Fi channels for its configured country.
if command -v raspi-config >/dev/null 2>&1; then
  read -r -p "Wi-Fi country code [IN]: " WIFI_COUNTRY
  WIFI_COUNTRY="${WIFI_COUNTRY:-IN}"
  raspi-config nonint do_wifi_country "$WIFI_COUNTRY"
fi

nmcli radio wifi on

# Reuse the connection on repeated runs so the script is safe to rerun.
if nmcli -t -f NAME connection show | grep -Fxq "$HOTSPOT_CONNECTION"; then
  nmcli connection modify "$HOTSPOT_CONNECTION" \
    connection.interface-name "$WIFI_IFACE" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    802-11-wireless.ssid "$HOTSPOT_SSID" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.channel 6 \
    ipv4.method shared \
    ipv4.addresses "$PI_HOTSPOT_IP" \
    ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASSWORD"
else
  nmcli connection add type wifi ifname "$WIFI_IFACE" con-name "$HOTSPOT_CONNECTION" ssid "$HOTSPOT_SSID"
  nmcli connection modify "$HOTSPOT_CONNECTION" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.channel 6 \
    ipv4.method shared \
    ipv4.addresses "$PI_HOTSPOT_IP" \
    ipv6.method disabled \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASSWORD"
fi

unset HOTSPOT_PASSWORD
nmcli connection up "$HOTSPOT_CONNECTION"

cat <<EOF

Hotspot configured and set to start automatically at boot.
Wi-Fi name: $HOTSPOT_SSID
Pi address: 10.42.0.1
Connect your phone/laptop to the Wi-Fi, then open:
  Backend API: http://10.42.0.1:8000/docs
  Local app:   http://10.42.0.1:8000/  (after the frontend build is installed on the Pi)

This hotspot has no internet uplink. The backend, camera, and Arduino run locally.
EOF
