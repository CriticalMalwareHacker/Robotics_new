"""Parking violation ticket: High-contrast Pillow image formatted for 58 mm thermal printers.

Width is 384 dots (THERMAL_PRINT_WIDTH_PX). Uses clean visual hierarchy, inverted
brand & violation banners, boxed registration plate, scannable QR verification code,
and bottom margin buffer for thermal printer tear bars.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.printer import THERMAL_PRINT_WIDTH_PX

W = THERMAL_PRINT_WIDTH_PX
MARGIN = 14

_lock = threading.Lock()
_seq = 0
_history_path = Path("app/database/parking_tickets.json")


def get_history() -> list[dict]:
    """Return saved parking tickets, newest first."""
    try:
        data = json.loads(_history_path.read_text(encoding="utf-8"))
        return list(reversed(data)) if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def record_ticket(ticket: dict) -> dict:
    """Persist a ticket record so history survives backend restarts."""
    with _lock:
        try:
            existing = json.loads(_history_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except (OSError, json.JSONDecodeError):
            existing = []
        existing.append(ticket)
        _history_path.parent.mkdir(parents=True, exist_ok=True)
        _history_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        LAST["ticket"] = ticket
    return ticket


LAST: dict = {"ticket": (get_history()[0] if get_history() else None)}


def next_number() -> str:
    global _seq
    with _lock:
        today = datetime.now().strftime("%y%m%d")
        persisted = get_history()
        matching = [str(row.get("number", "")) for row in persisted
                    if str(row.get("number", "")).startswith(f"T-{today}-")]
        highest = max((int(number.rsplit("-", 1)[-1]) for number in matching
                       if number.rsplit("-", 1)[-1].isdigit()), default=0)
        _seq = max(_seq, highest) + 1
        return f"T-{datetime.now().strftime('%y%m%d')}-{_seq:03d}"


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Find the best available TrueType font on Linux/Pi, macOS, or Windows."""
    candidates = [
        # Linux (Raspberry Pi OS)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Pillow 10+ scalable default font fallback
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def format_violation_title(raw_violation: str) -> str:
    mapping = {
        "OUTSIDE_SLOT": "PARKED OUTSIDE BAY",
        "STRADDLING": "BAY STRADDLING / DOUBLE BAY",
        "WRONG_ORIENTATION": "WRONG HEADING / ANGLE",
        "NO_PARKING_ZONE": "UNAUTHORIZED / NO-PARK ZONE",
        "LEGAL": "LEGAL (NO INFRACTION)",
    }
    return mapping.get(raw_violation.upper(), raw_violation.replace("_", " ").upper())


def build_ticket_image(number: str, when: str, plate: str, vehicle: str,
                       slot: str, violation: str) -> Image.Image:
    """Render a crisp, high-contrast 384 px monochrome citation image."""
    fonts = {
        "header_title": get_font(20, bold=True),
        "header_sub": get_font(11, bold=True),
        "section_tag": get_font(11, bold=True),
        "label": get_font(12, bold=False),
        "value": get_font(13, bold=True),
        "plate": get_font(25, bold=True),
        "violation": get_font(14, bold=True),
        "small": get_font(10, bold=False),
        "small_bold": get_font(11, bold=True),
    }

    # Initial canvas with generous vertical room
    img = Image.new("RGB", (W, 600), "white")
    d = ImageDraw.Draw(img)

    y = 6
    # 1. Top Inverted Black Brand Banner
    banner_height = 50
    d.rectangle([MARGIN, y, W - MARGIN, y + banner_height], fill="black")

    title_text = "PARKSENSEI"
    sub_text = "[ OFFICIAL PARKING CITATION ]"

    tw = d.textlength(title_text, font=fonts["header_title"])
    d.text(((W - tw) / 2, y + 6), title_text, fill="white", font=fonts["header_title"])

    sw = d.textlength(sub_text, font=fonts["header_sub"])
    d.text(((W - sw) / 2, y + 31), sub_text, fill="white", font=fonts["header_sub"])

    y += banner_height + 10

    # 2. Metadata Section (Clean Left & Right align)
    def draw_row(label: str, val: str, cur_y: int):
        d.text((MARGIN + 6, cur_y), label, fill="black", font=fonts["label"])
        vw = d.textlength(val, font=fonts["value"])
        d.text((W - MARGIN - 6 - vw, cur_y), val, fill="black", font=fonts["value"])

    draw_row("CITATION NO:", number, y); y += 19
    draw_row("DATE / TIME:", when, y); y += 19
    draw_row("LOCATION:", f"BAY {slot.upper()}", y); y += 19
    draw_row("PATROL UNIT:", "AUTONOMOUS UNIT #1", y); y += 22

    # Divider line
    d.line([MARGIN + 4, y, W - MARGIN - 4, y], fill="black", width=1)
    y += 10

    # 3. Boxed Vehicle Plate (Focal Point)
    plate_box_h = 62
    d.rectangle([MARGIN + 4, y, W - MARGIN - 4, y + plate_box_h], outline="black", width=2)
    tag_text = "VEHICLE REGISTRATION MARK"
    tag_w = d.textlength(tag_text, font=fonts["section_tag"])
    d.text(((W - tag_w) / 2, y + 6), tag_text, fill="black", font=fonts["section_tag"])

    clean_plate = plate.strip().upper() or "UNREAD"
    pw = d.textlength(clean_plate, font=fonts["plate"])
    d.text(((W - pw) / 2, y + 22), clean_plate, fill="black", font=fonts["plate"])
    y += plate_box_h + 10

    # 4. Inverted Infraction Box
    v_box_h = 48
    d.rectangle([MARGIN + 4, y, W - MARGIN - 4, y + v_box_h], fill="black")
    v_tag = "INFRACTION OBSERVED"
    v_tw = d.textlength(v_tag, font=fonts["section_tag"])
    d.text(((W - v_tw) / 2, y + 5), v_tag, fill="white", font=fonts["section_tag"])

    v_name = format_violation_title(violation)
    vn_w = d.textlength(v_name, font=fonts["violation"])
    d.text(((W - vn_w) / 2, y + 23), v_name, fill="white", font=fonts["violation"])
    y += v_box_h + 12

    # 5. QR Code for verification
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(f"http://10.42.0.1:8000/history?ticket={number}")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_w, qr_h = qr_img.size
        qr_x = int((W - qr_w) / 2)
        img.paste(qr_img, (qr_x, y))
        y += qr_h + 4

        verify_text = "SCAN TO VERIFY RECORD"
        vvw = d.textlength(verify_text, font=fonts["small_bold"])
        d.text(((W - vvw) / 2, y), verify_text, fill="black", font=fonts["small_bold"])
        y += 18
    except Exception:
        # Graceful fallback if qrcode is not present
        pass

    # 6. Dotted Perforation Line & Disclaimer
    for x in range(MARGIN, W - MARGIN, 8):
        d.line([x, y, x + 4, y], fill="black", width=1)
    y += 9

    disc1 = "ACADEMIC PROTOTYPE ONLY"
    disc2 = "NOT AN OFFICIAL TRAFFIC FINE"
    d1_w = d.textlength(disc1, font=fonts["small_bold"])
    d.text(((W - d1_w) / 2, y), disc1, fill="black", font=fonts["small_bold"]); y += 15

    d2_w = d.textlength(disc2, font=fonts["small"])
    d.text(((W - d2_w) / 2, y), disc2, fill="black", font=fonts["small"]); y += 22

    # 7. Generous bottom buffer so the physical tear bar / cutter never slices text
    final_h = y + 14
    final_img = img.crop((0, 0, W, final_h))

    # Outer border frame
    final_draw = ImageDraw.Draw(final_img)
    final_draw.rectangle([2, 2, W - 3, final_h - 3], outline="black", width=2)

    return final_img


def save_ticket_png(image: Image.Image, number: str) -> str:
    """Persist PNG for the HUD preview + reprint; returns public URL path."""
    outdir = Path("generated_labels")
    outdir.mkdir(exist_ok=True)
    name = f"ticket_{number.replace('/', '-')}.png"
    image.save(outdir / name, "PNG")
    return f"/generated_labels/{name}"
