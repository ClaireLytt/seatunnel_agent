"""Per-session connection registry for the Data Comparison page.

Gradio-free: this module replaces the former module-closure ``holder`` dict in
``ui.py``. Each :class:`SessionState` carries the connection/table/report/
schedule state for one user session, plus its own lock; the
:class:`ConnectionRegistry` keys sessions by an opaque id so a future REST
layer can issue and look up per-user sessions.

The Gradio page creates one session per page render (``render_data_comparison_
page`` runs once per process in the hub), which preserves today's
process-global semantics exactly.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    """Mutable per-session state, guarded by its own ``lock``.

    Fields mirror the legacy ``holder`` dict one-to-one:
    executors A/B, table lists, last report, and schedule timer state.
    """

    session_id: str
    executor_a: Any | None = None
    executor_b: Any | None = None
    tables_a: list[str] = field(default_factory=list)
    tables_b: list[str] = field(default_factory=list)
    last_report: Any | None = None
    schedule_timer: threading.Timer | None = None
    schedule_active: bool = False
    schedule_interval: int = 0
    schedule_request: Any | None = None
    schedule_last_run: str | None = None
    schedule_last_error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


#: Default cap on live sessions (seatunnel-style cap+evict): each session
#: can hold two DB executors and a timer, so an unbounded registry leaks.
_DEFAULT_MAX_SESSIONS = 100


class ConnectionRegistry:
    """Thread-safe map of session id -> :class:`SessionState`.

    Capped at ``max_sessions``: :meth:`create` evicts the oldest session
    without an active schedule first (dict order = creation order).
    Sessions with ``schedule_active`` are never evicted — killing a user's
    scheduled comparison to admit a new tab would be worse than briefly
    exceeding the cap.
    """

    def __init__(self, max_sessions: int = _DEFAULT_MAX_SESSIONS) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions

    def create(self) -> SessionState:
        """Create and register a new session with a fresh id.

        Evicts (via :meth:`remove`, which cancels timers) the oldest
        idle session when the registry is at capacity.
        """
        while True:
            with self._lock:
                if len(self._sessions) < self._max_sessions:
                    break
                victim = next(
                    (sid for sid, s in self._sessions.items()
                     if not s.schedule_active),
                    None,
                )
            if victim is None:  # every session has an active schedule
                break
            self.remove(victim)
        session = SessionState(session_id=uuid.uuid4().hex)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        """Drop a session, cancelling any scheduled-comparison timer.

        A timer left behind by an evicted session would keep firing
        against dead executors forever; eviction must cancel it.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return
        with session.lock:
            session.schedule_active = False
            timer = session.schedule_timer
            session.schedule_timer = None
        if timer is not None:
            timer.cancel()


_registry = ConnectionRegistry()


def get_registry() -> ConnectionRegistry:
    """Return the process-wide registry singleton."""
    return _registry
