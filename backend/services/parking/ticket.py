"""Parking violation ticket: Pillow image sized for the 58 mm printer.

Width is always 384 dots (`THERMAL_PRINT_WIDTH_PX`). The same PNG is shown
in the HUD ticket card and sent through the existing printer service
(`print_label`), never by opening the device node here.
"""

from __future__ import annotations

import threading
from datetime import datetime
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.printer import THERMAL_PRINT_WIDTH_PX

W = THERMAL_PRINT_WIDTH_PX
MARGIN = 12

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


def build_ticket_image(number: str, when: str, plate: str, vehicle: str,
                       slot: str, violation: str) -> Image.Image:
    """Render a legible, printer-width parking notice as an RGB image."""
    # Use a scalable font when available, while retaining compatibility with
    # minimal Raspberry Pi/Pillow installations that only have the bitmap font.
    font_paths = {
        "regular": (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ),
        "bold": (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ),
    }

    def load_font(kind: str, size: int):
        for path in font_paths[kind]:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    fonts = {
        "brand": load_font("bold", 17),
        "title": load_font("bold", 23),
        "section": load_font("bold", 13),
        "body": load_font("regular", 15),
        "body_bold": load_font("bold", 16),
        "small": load_font("regular", 12),
    }

    # Measure and lay out first so long IDs and violation names wrap instead
    # of being clipped at the 58 mm printer's 384-dot width.
    img = Image.new("RGB", (W, 10), "white")
    d = ImageDraw.Draw(img)
    inner_left, inner_right = MARGIN + 5, W - MARGIN - 5
    content_width = inner_right - inner_left
    blocks: list[tuple[str, object, int, str]] = []
    y = MARGIN + 5

    def add_text(text: str, font, *, align: str = "left", gap: int = 3):
        nonlocal y
        box = d.textbbox((0, 0), text or " ", font=font)
        height = box[3] - box[1]
        blocks.append((text, font, y, align))
        y += height + gap

    def add_wrapped(label: str, value: str, font, *, gap: int = 4):
        nonlocal y
        text = f"{label}: {value or '—'}" if label else (value or '—')
        words = text.split()
        rows: list[str] = []
        row = ""
        for word in words:
            candidate = f"{row} {word}".strip()
            if row and d.textlength(candidate, font=font) > content_width:
                rows.append(row)
                row = word
            else:
                row = candidate
        if row:
            rows.append(row)
        for line in rows:
            add_text(line, font, gap=1)
        y += gap

    add_text("PARKSENSEI", fonts["brand"], align="center", gap=2)
    # A double rule separates the brand from the actual notice.
    y += 2
    blocks.append(("RULE", None, y, ""))
    y += 9
    add_text("PARKING NOTICE", fonts["title"], align="center", gap=1)
    add_text("ACADEMIC PROTOTYPE  •  NOT A FINE", fonts["small"], align="center", gap=8)

    add_wrapped("Ticket", number, fonts["body"])
    add_wrapped("Issued", when, fonts["body"])

    # Enclosed vehicle identifier is the most useful item to spot at a glance.
    y += 3
    plate_box_top = y
    plate_box_height = 58
    blocks.append(("PLATE_BOX", None, plate_box_top, ""))
    y += 6
    add_text("VEHICLE PLATE", fonts["section"], align="center", gap=1)
    add_text(plate or "—", fonts["title"], align="center", gap=5)
    blocks.append(("PLATE_BOX_END", None, y, ""))
    y += 8

    add_wrapped("Vehicle", vehicle, fonts["body"])
    add_wrapped("Parking bay", slot, fonts["body"])

    y += 2
    blocks.append(("RULE", None, y, ""))
    y += 8
    add_text("OBSERVED VIOLATION", fonts["section"], gap=3)
    add_wrapped("", violation.replace("_", " ").replace("-", " ").upper(),
                fonts["body_bold"], gap=4)

    y += 3
    blocks.append(("RULE", None, y, ""))
    y += 8
    add_text("Academic prototype only.", fonts["small"], align="center", gap=1)
    add_text("This notice is not a real fine.", fonts["small"], align="center", gap=5)
    height = y + MARGIN + 2

    out = Image.new("RGB", (W, height), "white")
    draw = ImageDraw.Draw(out)
    # Thin outer frame with generous printer-safe inset.
    draw.rectangle([2, 2, W - 3, height - 3], outline="black", width=2)
    for kind, _font, block_y, align in blocks:
        if kind == "RULE":
            draw.line((inner_left, block_y, inner_right, block_y), fill="black", width=1)
        elif kind == "PLATE_BOX":
            draw.rectangle((inner_left, block_y, inner_right, block_y + plate_box_height),
                           outline="black", width=2)
        elif kind == "PLATE_BOX_END":
            draw.line((inner_left, block_y, inner_right, block_y), fill="black", width=1)
        else:
            text, font = kind, _font
            if align == "center":
                text_width = draw.textlength(text, font=font)
                x = (W - text_width) / 2
            else:
                x = inner_left
            draw.text((x, block_y), text, fill="black", font=font)
    return out


def save_ticket_png(image: Image.Image, number: str) -> str:
    """Persist PNG for the HUD preview + reprint; returns public URL path."""
    outdir = Path("generated_labels")
    outdir.mkdir(exist_ok=True)
    name = f"ticket_{number.replace('/', '-')}.png"
    image.save(outdir / name, "PNG")
    return f"/generated_labels/{name}"
