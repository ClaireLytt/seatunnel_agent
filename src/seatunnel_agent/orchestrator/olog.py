# -*- coding: utf-8 -*-
"""Orchestrator chat persistence — JSONL, one line per completed turn.

Stores the plain-text transcript (request + final reply + tool-step labels),
never the provider message objects, so a session can be re-displayed and
re-seeded as plain alternating messages after a page refresh.  Env knobs:
``ORCH_CHAT_LOG=0`` disables, ``ORCH_CHAT_PATH`` relocates.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_LOG_BYTES = 10 * 1024 * 1024
_MAX_TEXT = 8000


def log_path() -> Path:
    return Path(os.getenv("ORCH_CHAT_PATH") or "logs/orchestrator_chat.jsonl")


class ChatLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._lock = threading.Lock()

    def log_turn(self, session_id: str, request: str, reply: str,
                 steps: list[dict[str, Any]] | None = None) -> None:
        """Best-effort append; never raises into the chat."""
        if os.getenv("ORCH_CHAT_LOG", "1") == "0":
            return
        try:
            rec = {
                "ts": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "session": session_id,
                "request": (request or "")[:_MAX_TEXT],
                "reply": (reply or "")[:_MAX_TEXT],
                "steps": [{"tool": s.get("tool"),
                           "elapsed_ms": s.get("elapsed_ms")}
                          for s in steps or []],
            }
            line = json.dumps(rec, ensure_ascii=False)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if (self.path.is_file()
                        and self.path.stat().st_size > _MAX_LOG_BYTES):
                    lines = self.path.read_text(
                        encoding="utf-8").splitlines()
                    self.path.write_text(
                        "\n".join(lines[len(lines) // 2:]) + "\n",
                        encoding="utf-8")
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:  # noqa: BLE001 — persistence is best-effort
            pass

    def last_session(self) -> list[dict[str, Any]]:
        """All turns of the most recent session, oldest first."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        turns: list[dict[str, Any]] = []
        for line in lines:
            try:
                turns.append(json.loads(line))
            except ValueError:
                continue
        if not turns:
            return []
        last_id = turns[-1].get("session")
        return [t for t in turns if t.get("session") == last_id]
