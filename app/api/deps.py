"""Shared auth for robot routers: optional shared API key.

How it works (see docs/REMOTE_ARCHITECTURE.md):
- Pi sets API_KEY in its .env (random token, never committed).
- Deployed frontend stores the same value as VITE_API_KEY and sends it as
  `Authorization: Bearer <key>` (or `X-API-Key: <key>`).
- If API_KEY is unset/empty (laptop dev), routes stay OPEN so tests and local
  work need no keys. Existing PrintSensei routes are untouched (no auth).
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


def require_api_key(authorization: str | None = Header(default=None),
                    x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_KEY", "").strip()
    if not expected:
        return  # open local dev / laptop tests
    provided = None
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):].strip()
    elif x_api_key:
        provided = x_api_key.strip()
    if provided != expected:
        raise HTTPException(status_code=401,
                            detail="Missing or invalid API key.")
