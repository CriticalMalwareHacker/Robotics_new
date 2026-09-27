"""Persistent history service for PrintSensei labels and diagrams."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

HISTORY_FILE = Path("app/database/history.json")


def _get_diagram_title_hint(filename: str) -> tuple[str, str, str]:
    """Provide a friendly name for known or discovered diagram files."""
    name_lower = filename.lower()
    if "09f7883e" in name_lower:
        return "BMW Engine Overview", "Diagram with labels & internals", "study"
    if "a7ca95fd" in name_lower:
        return "Arduino Mega 2560", "ATmega2560 pinout & board diagram", "study"
    if "smoke" in name_lower:
        return "Smoke Test Print", "58mm test pattern", "study"
    return f"Study Diagram ({filename[:12]})", "AI generated educational diagram", "study"


def _seed_history_if_needed() -> list[dict[str, Any]]:
    """Seed history from actual generated diagrams in diagram_images directory."""
    items: list[dict[str, Any]] = []
    diagram_dir = Path("diagram_images")
    if diagram_dir.exists():
        # Get all non-thermal pngs sorted by modification time (newest first)
        pngs = [
            p for p in diagram_dir.glob("*.png")
            if not p.name.endswith("_thermal.png") and not p.name.startswith("reference_")
        ]
        pngs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        for p in pngs[:15]:
            title, desc, mode = _get_diagram_title_hint(p.name)
            mtime = p.stat().st_mtime
            t_str = time.strftime("%H:%M", time.localtime(mtime))
            items.append({
                "id": f"diag_{p.stem}",
                "title": title,
                "desc": desc,
                "mode": mode,
                "time": t_str,
                "image_url": f"/generated-images/{p.name}",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime)),
            })
    return items


def get_all_history() -> list[dict[str, Any]]:
    """Return all print history items, newest first."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass

    # Initialize from actual diagrams
    seeded = _seed_history_if_needed()
    save_history(seeded)
    return seeded


def save_history(items: list[dict[str, Any]]) -> None:
    """Save history items to disk."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(items[:50], f, indent=2)


def add_history_entry(title: str, desc: str, mode: str, image_url: str | None = None) -> dict[str, Any]:
    """Add a new print entry to history."""
    items = get_all_history()
    now = time.time()
    entry = {
        "id": f"hist_{int(now * 1000)}",
        "title": title or "Printed Label",
        "desc": desc or "PrintSensei Label",
        "mode": mode or "study",
        "time": time.strftime("%H:%M", time.localtime(now)),
        "image_url": image_url or "",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }
    # Deduplicate if exact same image_url was added within last 5 seconds
    if items and items[0].get("image_url") == image_url and image_url:
        return items[0]

    items.insert(0, entry)
    save_history(items)
    return entry
