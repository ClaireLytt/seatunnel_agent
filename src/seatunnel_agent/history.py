"""Chat session persistence — save/load conversations as JSON files."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HISTORY_DIR = Path.home() / ".seatunnel-agent" / "chat_history"
_OLD_HISTORY_DIR = Path("chat_history")


@dataclass
class Session:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    chat_messages: list[dict[str, str]] = field(default_factory=list)
    agent_messages: list[dict[str, Any]] = field(default_factory=list)
    agent_context: dict[str, Any] = field(default_factory=dict)


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


_VALID_SESSION_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _session_path(session_id: str) -> Path:
    if not _VALID_SESSION_ID.match(session_id):
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return HISTORY_DIR / f"{session_id}.json"


def save_session(session: Session) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    session.updated_at = now_iso()
    data = asdict(session)
    _session_path(session.session_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session(session_id: str) -> Session | None:
    try:
        path = _session_path(session_id)
    except ValueError:
        return None
    if not path.exists():
        # Backward compatibility: check the old CWD-relative location
        old_path = _OLD_HISTORY_DIR / f"{session_id}.json"
        if old_path.exists():
            path = old_path
        else:
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
    try:
        path = _session_path(session_id)
    except ValueError:
        return
    if path.exists():
        path.unlink()


def list_sessions() -> list[dict[str, str]]:
    seen_ids: set[str] = set()
    sessions: list[dict[str, str]] = []

    # Collect from new location first, then fall back to old CWD-relative dir
    dirs_to_check: list[Path] = []
    if HISTORY_DIR.is_dir():
        dirs_to_check.append(HISTORY_DIR)
    if (
        _OLD_HISTORY_DIR.is_dir()
        and _OLD_HISTORY_DIR.resolve() != HISTORY_DIR.resolve()
    ):
        dirs_to_check.append(_OLD_HISTORY_DIR)

    for d in dirs_to_check:
        for f in d.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sid = data["session_id"]
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                msg_count = len(data.get("chat_messages", []))
                sessions.append({
                    "id": sid,
                    "title": data.get("title", "Untitled"),
                    "updated_at": data.get("updated_at", ""),
                    "msg_count": msg_count,
                })
            except (json.JSONDecodeError, KeyError):
                continue

    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions
