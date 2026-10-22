"""Tests for seatunnel_agent.common.sse — shared SSE streaming helper."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.common.sse import _NO_KEY, sse, sse_stream


def _events(resp: Any) -> list[dict[str, Any]]:
    """Parse ``data: {json}`` frames from a TestClient response."""
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    out = []
    for line in resp.text.split("\n\n"):
        line = line.strip()
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def _client() -> TestClient:
    router = APIRouter()

    @router.post("/ok")
    def ok():
        def work(emit):
            emit({"type": "step", "n": 1})
            emit({"type": "step", "n": 2})
            return {"type": "done", "reply": "好的"}

        return sse_stream(work)

    @router.post("/boom")
    def boom():
        def work(emit):
            emit({"type": "step", "n": 1})
            raise ValueError("炸了 boom")

        return sse_stream(work)

    @router.post("/mapped")
    def mapped():
        def work(emit):
            emit(("tool", 12))
            emit(("skipped", 0))
            return {"type": "done"}

        def map_step(item):
            kind, ms = item
            if kind == "skipped":
                return None  # dropped from the stream
            return {"type": "step", "tool": kind, "elapsed_ms": ms}

        return sse_stream(work, map_step=map_step)

    @router.post("/no-terminal")
    def no_terminal():
        def work(emit):
            emit({"event": "progress", "value": 0.5})
            emit({"event": "done", "html": "<b>x</b>"})
            return None  # noqa: RET501 — explicit: no terminal frame

        return sse_stream(work)

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestSseFraming:
    def test_frame_shape(self):
        assert sse({"a": 1}) == 'data: {"a": 1}\n\n'

    def test_no_ascii_escape(self):
        assert "中文" in sse({"msg": "中文"})

    def test_no_key_dict_bilingual(self):
        assert set(_NO_KEY) == {"en", "zh"}
        assert "API key" in _NO_KEY["en"]
        assert "LLM" in _NO_KEY["zh"]


class TestSseStream:
    def test_event_order_and_done(self):
        events = _events(_client().post("/ok"))
        assert events == [
            {"type": "step", "n": 1},
            {"type": "step", "n": 2},
            {"type": "done", "reply": "好的"},
        ]

    def test_exception_becomes_terminal_error(self):
        events = _events(_client().post("/boom"))
        assert events[0] == {"type": "step", "n": 1}
        assert events[-1] == {"type": "error",
                              "message": "ValueError: 炸了 boom"}
        assert len(events) == 2

    def test_map_step_serializes_and_drops(self):
        events = _events(_client().post("/mapped"))
        assert events == [
            {"type": "step", "tool": "tool", "elapsed_ms": 12},
            {"type": "done"},
        ]

    def test_none_return_means_no_terminal_frame(self):
        events = _events(_client().post("/no-terminal"))
        assert events == [
            {"event": "progress", "value": 0.5},
            {"event": "done", "html": "<b>x</b>"},
        ]

    def test_chinese_not_escaped_on_wire(self):
        resp = _client().post("/ok")
        assert "好的" in resp.text
        assert "\\u" not in resp.text
