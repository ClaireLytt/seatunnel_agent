# -*- coding: utf-8 -*-
"""Orchestrator chat persistence — JSONL, one line per completed turn.

Stores the plain-text transcript (request + final reply + tool-step labels),
never the provider message objects, so a session can be re-displayed and
re-seeded as plain alternating messages after a page refresh.  Env knobs:
``ORCH_CHAT_LOG=0`` disables, ``ORCH_CHAT_PATH`` relocates.

NOTE: the log is one local file for the whole app — restore is per
DEPLOYMENT, not per browser.  Fine for the single-user local tool this is;
a multi-user deployment should set ``ORCH_CHAT_LOG=0``.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.jsonl_log import JsonlLog

_MAX_TEXT = 8000


def log_path() -> Path:
    return Path(os.getenv("ORCH_CHAT_PATH") or "logs/orchestrator_chat.jsonl")


class ChatLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._log = JsonlLog(lambda: self.path, env_switch="ORCH_CHAT_LOG")

    def log_turn(self, session_id: str, request: str, reply: str,
                 steps: list[dict[str, Any]] | None = None) -> None:
        """Best-effort append; never raises into the chat."""
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
        except Exception:  # noqa: BLE001 — persistence is best-effort
            return
        self._log.append(rec)

    def mark_cleared(self) -> None:
        """Persist a "new session" boundary — restores stop at this point,
        so a cleared chat stays cleared across page refreshes."""
        self._log.append({"cleared": True})

    def last_session(self) -> list[dict[str, Any]]:
        """All turns of the most recent session (after the last cleared
        marker), oldest first."""
        turns: list[dict[str, Any]] = []
        for rec in self._log.recent(n=1_000_000):
            if rec.get("cleared"):
                turns = []
                continue
            turns.append(rec)
        if not turns:
            return []
        last_id = turns[-1].get("session")
        return [t for t in turns if t.get("session") == last_id]
