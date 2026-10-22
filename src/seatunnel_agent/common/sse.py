"""Shared SSE streaming helper — queue + daemon thread + sentinel.

Factored from the agent APIs (code_fix, web_task, orchestrator,
ui_testing, data_comparison …) which all stream one background run as
``data: {json}\n\n`` frames:

- ``sse(obj)``   — frame one dict (``ensure_ascii=False``).
- ``sse_stream(work, *, map_step=None)`` — run ``work(emit)`` in a
  daemon thread; every ``emit(item)`` is drained in the response
  generator (so serialization like ``step.to_dict()`` happens at drain
  time via ``map_step``), an exception becomes a terminal
  ``{"type": "error", "message": "Type: msg"}`` frame, and a dict
  returned by ``work`` becomes the terminal frame (return ``None`` if
  ``work`` emitted its own terminal frame).
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable, Iterator, Mapping
from typing import Any

from fastapi.responses import StreamingResponse

__all__ = ["_NO_KEY", "sse", "sse_stream"]

# Shared "no LLM configured" message (was duplicated verbatim in the
# code_fix and web_task APIs).
_NO_KEY = {
    "en": "No LLM configured — set an API key on the Settings page first.",
    "zh": "未配置 LLM — 请先到设置页配置 API key。",
}


def sse(obj: Mapping[str, Any]) -> str:
    """Frame one JSON object as an SSE ``data:`` event."""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def sse_stream(
    work: Callable[[Callable[[Any], None]], Mapping[str, Any] | None],
    *,
    map_step: Callable[[Any], Mapping[str, Any] | None] | None = None,
) -> StreamingResponse:
    """Run *work* in a daemon thread and stream its events as SSE.

    ``work(emit)`` runs in the thread; each ``emit(item)`` enqueues one
    event.  The response generator drains the queue and yields
    ``sse(map_step(item))`` for each item (default: the item itself,
    which must then be a dict; ``map_step`` returning ``None`` drops the
    item).  When *work* finishes:

    - an exception yields ``{"type": "error", "message": "Type: msg"}``
      as the terminal frame;
    - a returned mapping is yielded as the terminal frame;
    - ``None`` means *work* already emitted its terminal frame.
    """
    events: queue.Queue[Any] = queue.Queue()
    outcome: dict[str, Any] = {}
    _sentinel = object()

    def run() -> None:
        try:
            outcome["result"] = work(events.put)
        except Exception as exc:
            outcome["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            events.put(_sentinel)

    def stream() -> Iterator[str]:
        threading.Thread(target=run, daemon=True).start()
        while True:
            item = events.get()
            if item is _sentinel:
                break
            mapped = map_step(item) if map_step is not None else item
            if mapped is not None:
                yield sse(mapped)
        if "error" in outcome:
            yield sse({"type": "error", "message": outcome["error"]})
            return
        result = outcome.get("result")
        if result is not None:
            yield sse(result)

    return StreamingResponse(stream(), media_type="text/event-stream")
