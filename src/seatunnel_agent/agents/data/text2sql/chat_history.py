"""Text2SQL chat session persistence — save/load conversations as JSON files."""

from __future__ import annotations

import json
import re
import threading
import time as _time
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any

from seatunnel_agent.common.history import (  # noqa: F401 — shared session helpers (re-exported)
    extract_title,
    new_session_id,
    now_iso,
)
from seatunnel_agent.common.utils import write_json_atomic

HISTORY_DIR = Path.home() / ".seatunnel-agent" / "text2sql_history"

_VALID_SESSION_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass
class Text2SQLSession:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    ds_type: str = ""
    chat_messages: list[dict[str, str]] = field(default_factory=list)
    agent_messages: list[dict[str, Any]] = field(default_factory=list)


def _session_path(session_id: str) -> Path:
    if not _VALID_SESSION_ID.match(session_id):
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return HISTORY_DIR / f"{session_id}.json"


_MAX_AGENT_MESSAGES = 200
_MAX_CHAT_MESSAGES = 500


_sessions_cache: list[dict[str, str]] | None = None
_sessions_cache_ts: float = 0.0
_SESSIONS_CACHE_TTL = 5.0
_sessions_cache_lock = threading.Lock()

_T2S_FIELDS = {f.name for f in dc_fields(Text2SQLSession)}


def _invalidate_sessions_cache() -> None:
    global _sessions_cache
    with _sessions_cache_lock:
        _sessions_cache = None


def save_t2s_session(session: Text2SQLSession) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    session.updated_at = now_iso()
    if len(session.chat_messages) > _MAX_CHAT_MESSAGES:
        session.chat_messages = session.chat_messages[-_MAX_CHAT_MESSAGES:]
    if len(session.agent_messages) > _MAX_AGENT_MESSAGES:
        session.agent_messages = session.agent_messages[-_MAX_AGENT_MESSAGES:]
    write_json_atomic(_session_path(session.session_id), asdict(session))
    _invalidate_sessions_cache()


def load_t2s_session(session_id: str) -> Text2SQLSession | None:
    try:
        path = _session_path(session_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        filtered = {k: v for k, v in data.items() if k in _T2S_FIELDS}
        return Text2SQLSession(**filtered)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def list_t2s_sessions() -> list[dict[str, str]]:
    global _sessions_cache, _sessions_cache_ts
    with _sessions_cache_lock:
        if _sessions_cache is not None and (_time.time() - _sessions_cache_ts) < _SESSIONS_CACHE_TTL:
            return list(_sessions_cache)
    sessions: list[dict[str, str]] = []
    if not HISTORY_DIR.is_dir():
        return sessions
    for f in HISTORY_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "id": data["session_id"],
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
                "ds_type": data.get("ds_type", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    with _sessions_cache_lock:
        _sessions_cache = sessions
        _sessions_cache_ts = _time.time()
    return sessions
