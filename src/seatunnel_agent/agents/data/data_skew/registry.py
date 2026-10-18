"""Per-session connection registry for the Data Skew page.

Gradio-free, modeled on data_comparison.registry: each
:class:`SkewSession` carries one live DB executor plus its probe cache,
keyed by an opaque id so the REST layer can issue and look up per-tab
sessions (the React page stores the id in sessionStorage).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.agents.data.data_skew.probe import ProbeCache


@dataclass
class SkewSession:
    """Mutable per-session state, guarded by its own ``lock``.

    Fields mirror the legacy Gradio ``conn_state`` dict one-to-one:
    executor, ds_type, localized status line, probe cache.
    """

    session_id: str
    executor: Any | None = None
    ds_type: str = ""
    status: str = ""
    cache: ProbeCache = field(default_factory=ProbeCache)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def connected(self) -> bool:
        return self.executor is not None


#: Cap on live sessions (datacompare precedent): each session can hold a
#: DB executor, so an unbounded registry leaks connections.
_DEFAULT_MAX_SESSIONS = 100


class SkewRegistry:
    """Thread-safe map of session id -> :class:`SkewSession`.

    Capped at ``max_sessions``: :meth:`create` evicts the oldest session
    (dict order = creation order) — skew sessions have no long-lived
    background work, so plain FIFO eviction is safe.
    """

    def __init__(self, max_sessions: int = _DEFAULT_MAX_SESSIONS) -> None:
        self._sessions: dict[str, SkewSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions

    def create(self) -> SkewSession:
        with self._lock:
            while len(self._sessions) >= self._max_sessions:
                victim = next(iter(self._sessions))
                self._sessions.pop(victim, None)
            session = SkewSession(session_id=uuid.uuid4().hex)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> SkewSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


_registry = SkewRegistry()


def get_registry() -> SkewRegistry:
    """Return the process-wide registry singleton."""
    return _registry
