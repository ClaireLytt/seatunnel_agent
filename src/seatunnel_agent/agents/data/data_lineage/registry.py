"""Per-session graph registry for the Data Lineage page.

Gradio-free, modeled on data_skew.registry: each :class:`LineageSession`
holds one built :class:`LineageGraph` (the Gradio page kept it in
``gr.State``), keyed by an opaque id so the REST layer can build once and
answer many queries without re-parsing the source directories.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LineageSession:
    """Mutable per-session state, guarded by its own ``lock``."""

    session_id: str
    graph: Any | None = None          # LineageGraph | None
    warnings: list[str] = field(default_factory=list)
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def built(self) -> bool:
        return self.graph is not None


#: Cap on live sessions (skew/datacompare precedent): a built graph can be
#: large, so an unbounded registry leaks memory.
_DEFAULT_MAX_SESSIONS = 100

#: Idle TTL: a session untouched this long is swept on the next create/get.
_DEFAULT_TTL_SECONDS = 4 * 3600


class LineageRegistry:
    """Thread-safe map of session id -> :class:`LineageSession`."""

    def __init__(self, max_sessions: int = _DEFAULT_MAX_SESSIONS,
                 ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._sessions: dict[str, LineageSession] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds

    def _sweep_locked(self) -> None:
        cutoff = time.time() - self._ttl
        for sid in [sid for sid, s in self._sessions.items()
                    if s.last_used < cutoff]:
            self._sessions.pop(sid, None)

    def create(self) -> LineageSession:
        with self._lock:
            self._sweep_locked()
            while len(self._sessions) >= self._max_sessions:
                victim = next(iter(self._sessions))
                self._sessions.pop(victim, None)
            session = LineageSession(session_id=uuid.uuid4().hex)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> LineageSession | None:
        with self._lock:
            self._sweep_locked()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_used = time.time()
            return session

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


_registry = LineageRegistry()


def get_registry() -> LineageRegistry:
    """Return the process-wide registry singleton."""
    return _registry
