"""ESC/POS raster encoding and transport for thermal label printers (SHREYANS POSIFLOW 58D)."""

from __future__ import annotations

import fcntl
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from PIL import Image

from shared.config import HARDWARE_MODE

logger = logging.getLogger(__name__)

# Standard 58 mm thermal printer head width (203 DPI = ~8 dots/mm -> 48 mm printable = 384 dots)
THERMAL_PRINT_WIDTH_PX = 384
USBDEVFS_RESET = ord('U') << 8 | 20  # 0x5514 = 21780 ioctl


@dataclass(frozen=True)
class PrinterConfig:
    """Runtime configuration; environment variables make Pi deployment configurable."""

    device: str = os.getenv("PRINTER_DEVICE", "/dev/usb/lp0")
    cups_queue: str = os.getenv("CUPS_QUEUE", "POSIFLOW58D")
    use_cups: bool = os.getenv("PRINTER_USE_CUPS", "false").lower() in {"1", "true", "yes"}


def prepare_image_for_printing(image: Image.Image, target_width: int = THERMAL_PRINT_WIDTH_PX) -> Image.Image:
    """Creates a separate print-ready 1-bit monochrome image scaled to target width, keeping original image unchanged."""
    # 1. Handle transparency and alpha channels by compositing onto a white background
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[3])
        work_img = bg
    elif image.mode not in ("RGB", "L", "1"):
        work_img = image.convert("RGB")
    else:
        work_img = image.copy()

    # 2. Scale proportionally so width matches the thermal printer head width
    if work_img.width != target_width:
        aspect = work_img.height / work_img.width
        target_height = max(1, int(round(target_width * aspect)))
        work_img = work_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # 3. Convert to grayscale then 1-bit monochrome with Floyd-Steinberg dithering
    bw_image = work_img.convert("L").convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    # 4. Ensure width is divisible by 8 (pad right margin with white pixels if needed)
    padded_width = ((bw_image.width + 7) // 8) * 8
    if padded_width != bw_image.width:
        padded = Image.new("1", (padded_width, bw_image.height), 1)  # 1 = white dot
        padded.paste(bw_image, (0, 0))
        bw_image = padded

    return bw_image


def pil_to_escpos_raster(image: Image.Image, target_width: int = THERMAL_PRINT_WIDTH_PX) -> bytes:
    """Encode an image into ESC/POS initialization + GS v 0 raster payload."""
    img_1bit = prepare_image_for_printing(image, target_width=target_width)
    width, height = img_1bit.size
    width_bytes = width // 8

    # ESC @ (0x1B 0x40): Initialize/Reset printer hardware state and clear buffer
    init_cmd = b"\x1b\x40"

    # GS v 0 0 xL xH yL yH (0x1D 0x76 0x30 0x00 ...)
    raster_header = (
        b"\x1d\x76\x30\x00"
        + bytes([
            width_bytes & 0xFF,
            (width_bytes >> 8) & 0xFF,
            height & 0xFF,
            (height >> 8) & 0xFF,
        ])
    )

    packed = bytearray()
    pixels = img_1bit.load()
    for row in range(height):
        for byte_column in range(width_bytes):
            value = 0
            base_x = byte_column * 8
            for bit in range(8):
                # In mode "1", 0 = black (burn dot -> bit 1), 255/1 = white (no dot -> bit 0)
                if pixels[base_x + bit, row] == 0:
                    value |= 1 << (7 - bit)
            packed.append(value)

    # Feed extra lines so the printed label clears the manual tear bar
    feed = b"\n\n\n\n"
    return init_cmd + raster_header + bytes(packed) + feed


def _reset_usb_device(dev) -> bool:
    """Reset USB device via USBDEVFS_RESET ioctl to clear hardware bus halts."""
    try:
        bus = dev.bus
        address = dev.address
        dev_path = f"/dev/bus/usb/{bus:03d}/{address:03d}"
        if os.path.exists(dev_path):
            with open(dev_path, "wb") as f:
                fcntl.ioctl(f.fileno(), USBDEVFS_RESET, 0)
            time.sleep(0.5)
            return True
    except Exception as exc:
        logger.warning("USB device reset failed: %s", exc)
    return False


def _find_usb_printer():
    """Find USB thermal printer by Vendor/Product ID or USB Class 7."""
    try:
        import usb.core
        import usb.util
    except ImportError:
        return None

    # Try POSIFLOW 58D VID:PID (0456:0808)
    dev = usb.core.find(idVendor=0x0456, idProduct=0x0808)
    if dev:
        return dev

    # Try standard printer class (class 7)
    try:
        for d in usb.core.find(find_all=True):
            for cfg in d:
                for intf in cfg:
                    if intf.bInterfaceClass == 7:
                        return d
    except Exception:
        pass
    return None


def _write_pyusb(payload: bytes) -> tuple[bool, str]:
    """Write binary ESC/POS payload via direct PyUSB bulk transfer."""
    try:
        import usb.core
        import usb.util
    except ImportError:
        return False, "pyusb module not installed"

    dev = _find_usb_printer()
    if dev is None:
        return False, "USB thermal printer not found"

    def _attempt_stream(target_dev) -> tuple[bool, str]:
        # Detach kernel usblp if active
        try:
            if target_dev.is_kernel_driver_active(0):
                target_dev.detach_kernel_driver(0)
        except Exception:
            pass

        try:
            target_dev.set_configuration()
        except Exception:
            pass

        cfg = target_dev.get_active_configuration()
        intf = cfg[(0, 0)]
        ep_out = None
        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                ep_out = ep
                break

        if ep_out is None:
            return False, "Could not locate USB OUT endpoint"

        try:
            target_dev.clear_halt(ep_out.bEndpointAddress)
        except Exception:
            pass

        # Stream payload in chunks of 512 bytes with pacing to avoid hardware FIFO overflow
        chunk_size = 512
        total_written = 0
        total_len = len(payload)
        while total_written < total_len:
            chunk = payload[total_written : total_written + chunk_size]
            written = ep_out.write(chunk, timeout=3000)
            total_written += written
            if total_written < total_len:
                time.sleep(0.002)

        return True, f"Printed {total_written} bytes via PyUSB direct transfer"

    try:
        return _attempt_stream(dev)
    except Exception as first_err:
        logger.warning("First PyUSB attempt failed (%s), resetting device...", first_err)
        # Attempt USB reset and retry once
        _reset_usb_device(dev)
        dev = _find_usb_printer()
        if dev is None:
            return False, f"PyUSB retry failed: device lost after reset ({first_err})"
        try:
            return _attempt_stream(dev)
        except Exception as retry_err:
            return False, f"PyUSB stream failed: {retry_err}"


def _write_direct_device_node(device_path: str, payload: bytes) -> tuple[bool, str]:
    """Write binary ESC/POS payload directly to character device (e.g. /dev/usb/lp0) using safe chunking."""
    fd = os.open(device_path, os.O_WRONLY)
    try:
        chunk_size = 512
        total_written = 0
        total_len = len(payload)
        while total_written < total_len:
            chunk = payload[total_written : total_written + chunk_size]
            written = os.write(fd, chunk)
            total_written += written
            if total_written < total_len:
                time.sleep(0.002)
        return True, f"Printed {total_written} bytes via {device_path}"
    finally:
        os.close(fd)


def send_to_printer(payload: bytes, config: PrinterConfig | None = None) -> tuple[bool, str]:
    """Write raw ESC/POS bytes to printer using PyUSB direct transfer, /dev/usb/lp0, or CUPS fallback."""
    config = config or PrinterConfig()

    # 1. Primary path on Linux/Pi: PyUSB direct bulk transfer (bypasses usblp read bug)
    if not config.use_cups:
        success, msg = _write_pyusb(payload)
        if success:
            return True, msg

    # 2. Secondary path: Direct device node if available
    if not config.use_cups and os.path.exists(config.device):
        try:
            return _write_direct_device_node(config.device, payload)
        except OSError as exc:
            logger.warning("Direct device node write failed: %s", exc)

    # 3. Tertiary path: CUPS if configured or available
    if shutil.which("lp"):
        result = subprocess.run(
            ["lp", "-d", config.cups_queue, "-o", "raw"],
            input=payload,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return True, "Sent to printer via CUPS"
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        if config.use_cups:
            return False, detail or "CUPS rejected the print job"

    # 4. PC Simulation Mode
    if HARDWARE_MODE == "pc" or os.environ.get("MOCK_PRINTER", "").lower() in {"1", "true"}:
        return True, "Simulated print (PC mode): ESC/POS raster payload generated successfully"

    return False, f"Printer device not found or unable to communicate with POSIFLOW 58D"


def print_label(
    image: Image.Image,
    label_width_mm: int = 50,
    label_height_mm: int = 50,
    gap_mm: int = 2,
    config: PrinterConfig | None = None,
) -> tuple[bool, str]:
    """Encode image with ESC/POS GS v 0 raster and send to the POSIFLOW 58D printer."""
    payload = pil_to_escpos_raster(image, target_width=THERMAL_PRINT_WIDTH_PX)
    return send_to_printer(payload, config)
