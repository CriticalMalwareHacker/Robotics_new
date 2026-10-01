"""In-memory event bus feeding the HUD event log (latest 100 entries)."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

_events: deque[dict] = deque(maxlen=100)
_lock = threading.Lock()


def log(level: str, text: str) -> None:
    """Record an event. level in {"info", "warn", "error"}."""
    with _lock:
        _events.append({
            "t": datetime.now().strftime("%H:%M:%S"),
            "level": level if level in ("info", "warn", "error") else "info",
            "text": str(text)[:200],
        })


def latest(limit: int = 100) -> list[dict]:
    """Newest first (HUD renders top-down)."""
    with _lock:
        return list(reversed(list(_events)[-limit:]))


def clear() -> None:
    with _lock:
        _events.clear()
