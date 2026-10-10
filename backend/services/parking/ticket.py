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

from PIL import Image, ImageDraw

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
    """Render the violation notice; returns an RGB Pillow image (384 wide)."""
    lines = [
        ("PARKING VIOLATION", 28, True),
        ("NOTICE (DEMO)", 28, True),
        ("", 10, False),
        (f"Ticket  {number}", 20, False),
        (f"Date    {when}", 20, False),
        ("", 10, False),
        (f"Plate   {plate}", 22, False),
        (f"Vehicle {vehicle}", 20, False),
        (f"Slot    {slot}", 20, False),
        (f"Offence {violation}", 20, False),
        ("", 10, False),
        ("Academic prototype.", 18, False),
        ("Not a real fine.", 18, False),
    ]
    # dry-run height with default font
    tmp = Image.new("RGB", (W, 10), "white")
    d = ImageDraw.Draw(tmp)
    y = MARGIN
    heights: list[int] = []
    for text, size, _bold in lines:
        if not text:
            y += size
            heights.append(size)
            continue
        box = d.textbbox((0, 0), text)
        h = (box[3] - box[1]) + 6
        heights.append(h)
        y += h
    y += MARGIN

    img = Image.new("RGB", (W, y), "white")
    d = ImageDraw.Draw(img)
    y = MARGIN
    for (text, _size, _bold), h in zip(lines, heights):
        if text:
            box = d.textbbox((0, 0), text)
            w = box[2] - box[0]
            d.text(((W - w) / 2, y), text, fill="black")
        y += h
    # border
    d.rectangle([2, 2, W - 3, y - MARGIN + 6], outline="black", width=2)
    return img


def save_ticket_png(image: Image.Image, number: str) -> str:
    """Persist PNG for the HUD preview + reprint; returns public URL path."""
    outdir = Path("generated_labels")
    outdir.mkdir(exist_ok=True)
    name = f"ticket_{number.replace('/', '-')}.png"
    image.save(outdir / name, "PNG")
    return f"/generated_labels/{name}"
