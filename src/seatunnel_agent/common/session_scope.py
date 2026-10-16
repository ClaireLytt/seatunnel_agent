"""Per-browser-session state buckets for Gradio pages.

Gradio renders a page once at build time, so any plain dict created inside a
render function is shared by every browser session — user B's "Connect" would
overwrite user A's agent/db_config (state cross-talk). ``SessionScopedDict``
keeps the dict-style call sites but transparently resolves every operation to
a bucket keyed by the current request's ``session_hash`` (Gradio 6 sets
``gradio.context.LocalContext.request`` around each event callback, including
each ``next()`` of a generator callback).

Caveats:
- Background threads do NOT inherit the request contextvar. Capture the
  bucket with ``resolve()`` before spawning a thread and use that plain dict
  inside the thread.
- Outside any request (render time, CLI) a shared ``__default__`` bucket is
  used, which matches the old single-dict behaviour.
- Buckets are capped at ``_MAX_SESSIONS`` with LRU eviction, so memory does
  not grow without bound; an evicted (long-idle) session simply sees the
  page's initial "not connected" state again.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator, MutableMapping
from typing import Any

_MAX_SESSIONS = 128
_DEFAULT_KEY = "__default__"


def _current_session_key() -> str:
    try:
        from gradio.context import LocalContext

        request = LocalContext.request.get(None)
        session_hash = getattr(request, "session_hash", None)
        if session_hash:
            return str(session_hash)
    except Exception:
        pass
    return _DEFAULT_KEY


class SessionScopedDict(MutableMapping[str, Any]):
    """A dict whose contents are isolated per Gradio browser session."""

    def __init__(self, factory: Callable[[], dict[str, Any]]):
        self._factory = factory
        self._buckets: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def resolve(self) -> dict[str, Any]:
        """Return the current session's bucket (creating it if needed).

        Use this to pin the bucket before handing work to a background
        thread, where the request contextvar is no longer set.
        """
        key = _current_session_key()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = self._factory()
                self._buckets[key] = bucket
            self._buckets.move_to_end(key)
            while len(self._buckets) > _MAX_SESSIONS:
                self._buckets.popitem(last=False)
            return bucket

    def __getitem__(self, key: str) -> Any:
        return self.resolve()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.resolve()[key] = value

    def __delitem__(self, key: str) -> None:
        del self.resolve()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.resolve())

    def __len__(self) -> int:
        return len(self.resolve())
