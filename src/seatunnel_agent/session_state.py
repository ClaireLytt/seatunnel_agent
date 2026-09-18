"""Per-browser-session state for Gradio UIs.

Module-level holder dicts are shared by every browser session, so one
user's connection/agent/report state leaks into another's. Handlers
declare a ``request: gr.Request`` parameter (Gradio injects it without
wiring) and fetch their own holder via :meth:`SessionHolders.get`.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Callable


class SessionHolders:
    """session_hash → holder dict, LRU-bounded so dead sessions expire."""

    def __init__(
        self,
        factory: Callable[[], dict[str, Any]],
        max_sessions: int = 50,
    ) -> None:
        self._factory = factory
        self._max = max_sessions
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, request: Any = None) -> dict[str, Any]:
        # 直接调用（测试）或拿不到 session_hash 时退化为共享默认会话
        key = getattr(request, "session_hash", None) or "__default__"
        with self._lock:
            holder = self._store.get(key)
            if holder is None:
                holder = self._factory()
                self._store[key] = holder
                while len(self._store) > self._max:
                    self._store.popitem(last=False)
            else:
                self._store.move_to_end(key)
            return holder
