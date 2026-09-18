"""Text2SQL chat session persistence — save/load conversations as JSON files."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def extract_title(chat_messages: list[dict[str, str]], max_len: int = 30) -> str:
    for msg in chat_messages:
        if msg.get("role") == "user" and msg.get("content", "").strip():
            text = msg["content"].strip().replace("\n", " ")
            return text[:max_len] + ("..." if len(text) > max_len else "")
    return "Untitled"


def _session_path(session_id: str) -> Path:
    if not _VALID_SESSION_ID.match(session_id):
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return HISTORY_DIR / f"{session_id}.json"


_MAX_AGENT_MESSAGES = 200
_MAX_CHAT_MESSAGES = 500


def save_t2s_session(session: Text2SQLSession) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    session.updated_at = now_iso()
    if len(session.chat_messages) > _MAX_CHAT_MESSAGES:
        session.chat_messages = session.chat_messages[-_MAX_CHAT_MESSAGES:]
    if len(session.agent_messages) > _MAX_AGENT_MESSAGES:
        session.agent_messages = session.agent_messages[-_MAX_AGENT_MESSAGES:]
    path = _session_path(session.session_id)
    content = json.dumps(asdict(session), ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(HISTORY_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_t2s_session(session_id: str) -> Text2SQLSession | None:
    try:
        path = _session_path(session_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Text2SQLSession(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def delete_t2s_session(session_id: str) -> None:
    try:
        path = _session_path(session_id)
    except ValueError:
        return
    if path.exists():
        path.unlink()


def list_t2s_sessions() -> list[dict[str, str]]:
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
    return sessions
