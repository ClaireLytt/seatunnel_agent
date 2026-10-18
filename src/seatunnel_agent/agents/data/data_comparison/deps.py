"""Shared FastAPI-layer helpers for the /api/datacompare routers.

Lives in its own tiny module (not ``registry.py``) so the registry stays
framework-free: :func:`get_session_or_404` raises ``HTTPException`` and
the request bases are pydantic models, both FastAPI-layer concerns that
the pure comparison modules must not depend on.

Every router module (api / compound / features / generation / reports_api
/ schedule_api) imports from here instead of re-rolling its own
``_get_session`` and option-field clump.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from seatunnel_agent.agents.data.data_comparison.registry import (
    SessionState,
    get_registry,
)


def get_session_or_404(session_id: str) -> SessionState:
    """The registry session for *session_id*, or HTTP 404 when unknown."""
    session = get_registry().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return session


class SessionTablesRequest(BaseModel):
    """Base for requests addressing a session's selected table pair."""

    session_id: str
    table_a: str = ""
    table_b: str = ""
    lang: str = "en"


class OptionsRequest(SessionTablesRequest):
    """Base carrying the global options block (legacy ui.py:1810-1849).

    These fields ride on every comparison action request; names and
    defaults are frozen — the React page's ``CompareOptions`` matches
    them one-to-one.
    """

    where: str = ""
    # count
    threshold: str = ""
    # sample
    key_columns: str = ""
    strategy: str = "TOP N"
    column_mapping: str = ""
    masking: bool = True
    stratified_col: str = ""
