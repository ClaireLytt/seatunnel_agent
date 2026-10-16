"""Server-held Text2SQL sessions — the one home for session state (#99).

A session is always a :class:`SessionEntry` (agent + the connect params
that rebuild it on new-chat reset; ``connect=None`` for legacy stateless
/query callers). The manager owns the LRU store, the active-stream
registry and every lock; REST endpoints stay thin wiring.
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import OrderedDict
from typing import Any

_MAX_SESSIONS = 20


class SessionEntry:
    """Live agent plus the connect params that rebuild it on reset, and a
    small extras bag for session-scoped snapshots (e.g. the full schema
    store that table filtering widens back from)."""

    def __init__(self, agent: Any, connect: Any = None,
                 extras: dict[str, Any] | None = None) -> None:
        self.agent = agent
        self.connect = connect
        self.extras: dict[str, Any] = extras if extras is not None else {}


class SessionManager:
    """Thread-safe session lifecycle: create/get/replace, plus the
    one-active-stream-per-session rule with stop injection."""

    def __init__(self, max_size: int = _MAX_SESSIONS) -> None:
        self._max = max_size
        self._store: OrderedDict[str, SessionEntry] = OrderedDict()
        self._store_lock = threading.Lock()
        self._active: dict[str, queue.Queue] = {}
        self._active_lock = threading.Lock()

    # -- store -----------------------------------------------------------
    def create(self, agent: Any, connect: Any) -> str:
        session_id = uuid.uuid4().hex
        self._put(session_id, SessionEntry(agent, connect))
        return session_id

    def put_legacy(self, session_id: str, agent: Any) -> None:
        """Stateless /query callers supply their own key; same entry shape."""
        self._put(session_id, SessionEntry(agent, None))

    def replace_agent(self, session_id: str, agent: Any) -> SessionEntry | None:
        """Atomically swap the agent, keeping connect params; None when the
        session vanished (e.g. LRU-evicted) in the meantime."""
        with self._store_lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            new = SessionEntry(agent, entry.connect, dict(entry.extras))
            self._store[session_id] = new
            self._store.move_to_end(session_id)
            return new

    def get(self, session_id: str) -> SessionEntry | None:
        with self._store_lock:
            if session_id in self._store:
                self._store.move_to_end(session_id)
                return self._store[session_id]
        return None

    def _put(self, session_id: str, entry: SessionEntry) -> None:
        with self._store_lock:
            if session_id in self._store:
                self._store.move_to_end(session_id)
            self._store[session_id] = entry
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    # -- streams ---------------------------------------------------------
    def attach_stream(self, session_id: str) -> queue.Queue | None:
        """Register the one live stream for a session; None when busy."""
        q: queue.Queue = queue.Queue()
        with self._active_lock:
            if session_id in self._active:
                return None
            self._active[session_id] = q
        return q

    def finish_stream(self, session_id: str, q: queue.Queue) -> None:
        with self._active_lock:
            if self._active.get(session_id) is q:
                del self._active[session_id]

    def stop(self, session_id: str) -> bool:
        """Inject the terminal stop event into the live stream, if any."""
        with self._active_lock:
            q = self._active.get(session_id)
        if q is None:
            return False
        q.put(("final_answer", {"text": "", "stopped": True}))
        return True
