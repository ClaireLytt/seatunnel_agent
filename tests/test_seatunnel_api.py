"""In-process tests for the SeaTunnel Pipeline Builder REST API (/api/seatunnel).

Seam: the HTTP contract the React page consumes — same pattern as the
uitest / sql_review page API tests.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from seatunnel_agent.agents.data.seatunnel.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_meta_returns_modes_and_templates(client: TestClient) -> None:
    resp = client.get("/api/seatunnel/meta")
    assert resp.status_code == 200
    data = resp.json()

    # modes: the four legacy agent modes with both language labels
    modes = data["modes"]
    assert [m["key"] for m in modes] == ["nl", "run", "validate", "diagnose"]
    by_key = {m["key"]: m for m in modes}
    assert by_key["nl"]["en"] == "Natural Language"
    assert by_key["nl"]["zh"] == "自然语言描述"
    assert by_key["diagnose"]["en"] == "Diagnose Log"

    # templates: sourced from the built-in template catalog
    from seatunnel_agent.agents.data.seatunnel.templates import TEMPLATES

    templates = data["templates"]
    assert len(templates) == len(TEMPLATES)
    names = [t["name"] for t in templates]
    assert "fake_to_console" in names
    first = templates[names.index("fake_to_console")]
    assert first["description"].startswith("FakeSource")
    assert first["category"] == "testing"
    assert first["parameters"][0]["name"] == "rows"


def test_meta_default_config_path(client: TestClient) -> None:
    data = client.get("/api/seatunnel/meta").json()
    assert data["config_placeholder"] == "examples/fake_to_console.conf"


# ── Chat SSE (ticket 02) ─────────────────────────────────────────────


def _sse_events(resp) -> list[dict]:
    """Parse `data: <json>` frames from an SSE response body."""
    import json

    events = []
    for frame in resp.text.split("\n\n"):
        for line in frame.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


class _FakeAgent:
    """Emits the legacy event sequence through on_event, like SeaTunnelAgent."""

    instances: list[_FakeAgent] = []

    def __init__(self, settings, on_event=None):
        import threading

        self._on_event = on_event
        self.stop_event = threading.Event()
        self.chat_calls: list[str] = []
        type(self).instances.append(self)

    def _emit_turn(self, text: str) -> None:
        import json as _json

        self._on_event("step", {"iteration": 1, "max": 15, "phase": "thinking"})
        self._on_event("text_delta", {"text": text[:3]})
        self._on_event("text_delta", {"text": text[3:]})
        self._on_event("text", {"text": text})
        self._on_event("tool_call", {"name": "validate_config",
                                     "input": {"config_path": "x.conf"}})
        self._on_event("tool_result", {"name": "validate_config",
                                       "result": _json.dumps({"valid": True})})
        self._on_event("usage", {"input_tokens": 10, "output_tokens": 5})
        self._on_event("final_answer", {"text": text})

    def run(self, task: str) -> str:
        self._emit_turn("Hello")
        return "Hello"

    def chat(self, message: str) -> str:
        self.chat_calls.append(message)
        self._emit_turn("Again")
        return "Again"


@pytest.fixture()
def fake_agent(monkeypatch):
    from seatunnel_agent.agents.data.seatunnel import api

    _FakeAgent.instances = []
    monkeypatch.setattr(api, "SeaTunnelAgent", _FakeAgent)
    monkeypatch.setattr(api, "load_settings", lambda: object())
    api._CONVERSATIONS.clear()
    api.CONNECTION.update({"settings": None, "version": None})
    return _FakeAgent


def test_chat_streams_sse_events(client: TestClient, fake_agent) -> None:
    resp = client.post("/api/seatunnel/chat", json={"message": "build a pipeline"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(resp)
    # first frame announces the server-side conversation id
    assert events[0]["type"] == "conversation"
    assert events[0]["id"]

    types = [e["type"] for e in events]
    assert types.count("delta") == 2
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "Hello"

    # non-delta agent events arrive pre-rendered as legacy markdown
    by_kind = {e.get("kind"): e for e in events if e["type"] == "event"}
    assert "⏳ **Step 1** — Thinking..." in by_kind["step"]["markdown"]
    assert by_kind["text"]["markdown"] == "Hello"
    assert "**Tool Call: `validate_config`**" in by_kind["tool_call"]["markdown"]
    assert "Config is valid" in by_kind["tool_result"]["markdown"]
    assert "Tokens: 10 in / 5 out" in by_kind["usage"]["markdown"]

    # final frame closes the turn with elapsed seconds
    assert events[-1]["type"] == "final"
    assert isinstance(events[-1]["elapsed"], float)
    assert "error" not in events[-1]


def test_chat_second_turn_reuses_agent(client: TestClient, fake_agent) -> None:
    first = _sse_events(client.post("/api/seatunnel/chat",
                                    json={"message": "hi"}))
    cid = first[0]["id"]
    resp = client.post("/api/seatunnel/chat",
                       json={"message": "more", "conversation_id": cid})
    events = _sse_events(resp)
    assert events[0]["id"] == cid
    assert len(fake_agent.instances) == 1
    assert fake_agent.instances[0].chat_calls == ["more"]


def test_chat_without_settings_reports_no_settings(
    client: TestClient, monkeypatch,
) -> None:
    from seatunnel_agent.agents.data.seatunnel import api

    def _boom():
        raise RuntimeError("no .env")

    monkeypatch.setattr(api, "load_settings", _boom)
    api._CONVERSATIONS.clear()
    api.CONNECTION.update({"settings": None, "version": None})
    resp = client.post("/api/seatunnel/chat", json={"message": "hi"})
    events = _sse_events(resp)
    assert events[-1]["type"] == "final"
    msgs = [e for e in events if e["type"] == "event"]
    assert any("Settings not loaded" in e["markdown"] for e in msgs)


def test_chat_uses_connected_settings(client: TestClient, monkeypatch) -> None:
    """After Connect, chat must not need load_settings (ticket 03 handoff)."""
    from seatunnel_agent.agents.data.seatunnel import api
    from seatunnel_agent.common import settings_store

    _FakeAgent.instances = []
    monkeypatch.setattr(api, "SeaTunnelAgent", _FakeAgent)

    def _boom():
        raise RuntimeError("must not be called")

    monkeypatch.setattr(api, "load_settings", _boom)
    api._CONVERSATIONS.clear()
    api.CONNECTION.update({"settings": object(),
                           "version": settings_store.get_version()})
    resp = client.post("/api/seatunnel/chat", json={"message": "hi"})
    events = _sse_events(resp)
    assert events[-1]["type"] == "final"
    assert "error" not in events[-1]
    assert len(_FakeAgent.instances) == 1


def test_chat_empty_message_rejected(client: TestClient, fake_agent) -> None:
    resp = client.post("/api/seatunnel/chat", json={"message": "   "})
    assert resp.status_code == 400


class _BlockingAgent(_FakeAgent):
    """Streams a partial reply then blocks until stop_event is set."""

    def run(self, task: str) -> str:
        self._on_event("text_delta", {"text": "partial "})
        self._on_event("text_delta", {"text": "reply"})
        self.stop_event.wait(timeout=10)
        return ""


def test_stop_interrupts_stream_and_keeps_partial(monkeypatch) -> None:
    # Drives the endpoint's SSE generator directly: TestClient buffers the
    # whole response before returning, so mid-stream Stop needs this seam.
    import json as _json

    from seatunnel_agent.agents.data.seatunnel import api

    _BlockingAgent.instances = []
    monkeypatch.setattr(api, "SeaTunnelAgent", _BlockingAgent)
    monkeypatch.setattr(api, "load_settings", lambda: object())
    api._CONVERSATIONS.clear()
    api.CONNECTION.update({"settings": None, "version": None})

    resp = api.chat_stream(api.ChatRequest(message="hi"))
    assert resp.media_type == "text/event-stream"

    events: list[dict] = []

    async def consume() -> None:
        cid = ""
        async for frame in resp.body_iterator:
            for line in str(frame).split("\n"):
                if not line.startswith("data: "):
                    continue
                ev = _json.loads(line[6:])
                events.append(ev)
                if ev["type"] == "conversation":
                    cid = ev["id"]
                elif ev["type"] == "delta" and ev["text"] == "reply":
                    # agent now blocked mid-turn: Stop ends the stream
                    api.chat_stop(api.StopRequest(conversation_id=cid))

    import asyncio

    asyncio.run(asyncio.wait_for(consume(), timeout=15))

    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "partial reply"  # partial reply stayed
    assert events[-1]["type"] == "final"
    assert events[-1]["stopped"] is True
    assert _BlockingAgent.instances[0].stop_event.is_set()


def test_chat_409_when_turn_running(client: TestClient, fake_agent) -> None:
    from seatunnel_agent.agents.data.seatunnel import api

    cid = "busy"
    conv = api._CONVERSATIONS.setdefault(cid, api._Conversation())
    import queue as _queue

    conv.queue = _queue.Queue()
    resp = client.post("/api/seatunnel/chat",
                       json={"message": "hi", "conversation_id": cid})
    assert resp.status_code == 409


def test_stop_unknown_conversation_404(client: TestClient, fake_agent) -> None:
    resp = client.post("/api/seatunnel/chat/stop",
                       json={"conversation_id": "nope"})
    assert resp.status_code == 404


# ── Connect (ticket 03) ────────────────────────────────────────────────────


def test_connect_success_returns_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from seatunnel_agent.common import config

    settings = config.Settings(api_key="k", model_name="claude-test-model")
    monkeypatch.setattr(config, "load_settings", lambda: settings)

    resp = client.post("/api/seatunnel/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["model"] == "claude-test-model"


def test_connect_failure_returns_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from seatunnel_agent.common import config

    def _boom() -> config.Settings:
        raise ValueError("no API key configured")

    monkeypatch.setattr(config, "load_settings", _boom)

    resp = client.post("/api/seatunnel/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "no API key configured" in data["error"]


def test_connect_failure_clears_stored_settings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed connect must not leave stale settings behind (legacy parity)."""
    from seatunnel_agent.agents.data.seatunnel import api as st_api
    from seatunnel_agent.common import config

    settings = config.Settings(api_key="k", model_name="m")
    monkeypatch.setattr(config, "load_settings", lambda: settings)
    assert client.post("/api/seatunnel/connect").json()["ok"] is True
    assert st_api.CONNECTION["settings"] is settings

    def _boom() -> config.Settings:
        raise ValueError("gone")

    monkeypatch.setattr(config, "load_settings", _boom)
    assert client.post("/api/seatunnel/connect").json()["ok"] is False
    assert st_api.CONNECTION["settings"] is None
