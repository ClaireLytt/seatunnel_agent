"""Chat session persistence — save/load conversations as JSON files."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HISTORY_DIR = Path("chat_history")


@dataclass
class Session:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    chat_messages: list[dict[str, str]] = field(default_factory=list)
    agent_messages: list[dict[str, Any]] = field(default_factory=list)


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def extract_title(chat_messages: list[dict[str, str]], max_len: int = 30) -> str:
    for msg in chat_messages:
        if msg.get("role") == "user" and msg.get("content", "").strip():
            text = msg["content"].strip().replace("\n", " ")
            return text[:max_len] + ("..." if len(text) > max_len else "")
    return "Untitled"


def _session_path(session_id: str) -> Path:
    return HISTORY_DIR / f"{session_id}.json"


def save_session(session: Session) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    session.updated_at = _now_iso()
    data = asdict(session)
    _session_path(session.session_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session(session_id: str) -> Session | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def rename_session(session_id: str, new_title: str) -> bool:
    session = load_session(session_id)
    if session is None:
        return False
    session.title = new_title.strip() or session.title
    save_session(session)
    return True


def delete_session(session_id: str) -> None:
    path = _session_path(session_id)
    if path.exists():
        path.unlink()


def list_sessions() -> list[dict[str, str]]:
    if not HISTORY_DIR.is_dir():
        return []
    sessions = []
    for f in HISTORY_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "id": data["session_id"],
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions
