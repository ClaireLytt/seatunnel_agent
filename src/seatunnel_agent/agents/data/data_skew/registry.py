"""Per-session connection registry for the Data Skew page.

Gradio-free, modeled on data_comparison.registry: each
:class:`SkewSession` carries one live DB executor plus its probe cache,
keyed by an opaque id so the REST layer can issue and look up per-tab
sessions (the React page stores the id in sessionStorage).
"""

from __future__ import annotations

import threading
import time
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
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def connected(self) -> bool:
        return self.executor is not None


#: Cap on live sessions (datacompare precedent): each session can hold a
#: DB executor, so an unbounded registry leaks connections.
_DEFAULT_MAX_SESSIONS = 100

#: Idle TTL: a session untouched this long is swept on the next create/get
#: — an abandoned tab must not pin a DB executor until 100 newer sessions
#: push it out.
_DEFAULT_TTL_SECONDS = 4 * 3600


class SkewRegistry:
    """Thread-safe map of session id -> :class:`SkewSession`.

    Capped at ``max_sessions``: :meth:`create` evicts the oldest session
    (dict order = creation order) — skew sessions have no long-lived
    background work, so plain FIFO eviction is safe.
    """

    def __init__(self, max_sessions: int = _DEFAULT_MAX_SESSIONS,
                 ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._sessions: dict[str, SkewSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds

    def _sweep_locked(self) -> None:
        cutoff = time.time() - self._ttl
        for sid in [sid for sid, s in self._sessions.items()
                    if s.last_used < cutoff]:
            self._sessions.pop(sid, None)

    def create(self) -> SkewSession:
        with self._lock:
            self._sweep_locked()
            while len(self._sessions) >= self._max_sessions:
                victim = next(iter(self._sessions))
                self._sessions.pop(victim, None)
            session = SkewSession(session_id=uuid.uuid4().hex)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> SkewSession | None:
        with self._lock:
            self._sweep_locked()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_used = time.time()
            return session

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


_registry = SkewRegistry()


def get_registry() -> SkewRegistry:
    """Return the process-wide registry singleton."""
    return _registry
