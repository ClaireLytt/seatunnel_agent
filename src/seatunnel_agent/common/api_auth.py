"""Shared REST API-key auth (direction 6: open API for Dify/n8n).

Opt-in: when ``SEATUNNEL_API_KEY`` is set, every ``/api/*`` route requires a
matching ``X-API-Key`` header; when unset the API stays open (local/intranet
default, unchanged behavior). The dependency reads the env at request time
so tests and long-lived servers can toggle it without a restart.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

ENV_VAR = "SEATUNNEL_API_KEY"
HEADER = "X-API-Key"


async def require_api_key(request: Request) -> None:
    expected = os.getenv(ENV_VAR, "").strip()
    if not expected:
        return  # auth disabled — open API
    provided = request.headers.get(HEADER, "")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail=f"Missing or invalid {HEADER} header",
        )
