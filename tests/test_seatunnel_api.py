"""In-process tests for the SeaTunnel Pipeline Builder REST API (/api/seatunnel).

Seam: the HTTP contract the React page consumes — same pattern as the
uitest / sql_review page API tests.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

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

    def set_event_callback(self, on_event) -> None:
        self._on_event = on_event

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


# ── Sessions (ticket 04) ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def history_dir(monkeypatch, tmp_path):
    """Keep every test's history writes (chat persistence) off the real home dir."""
    from seatunnel_agent.common import history

    monkeypatch.setattr(history, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(history, "_OLD_HISTORY_DIR", tmp_path / "_old")
    return tmp_path


def _write_session(sid: str, title: str = "Old chat") -> None:
    from seatunnel_agent.common import history

    history.save_session(history.Session(
        session_id=sid,
        title=title,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        chat_messages=[
            {"role": "user", "content": "restore me"},
            {"role": "assistant", "content": "restored reply"},
        ],
        agent_messages=[{"role": "user", "content": "restore me"},
                        {"role": "assistant", "content": "restored reply"}],
        agent_context={"k": "v"},
    ))


def test_sessions_list_empty(client: TestClient, history_dir) -> None:
    resp = client.get("/api/seatunnel/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}


def test_sessions_listed_after_save(client: TestClient, history_dir) -> None:
    _write_session("abc123", title="My pipeline")
    data = client.get("/api/seatunnel/sessions").json()
    assert len(data["sessions"]) == 1
    s = data["sessions"][0]
    assert s["id"] == "abc123"
    assert s["title"] == "My pipeline"
    assert s["msg_count"] == 2
    assert s["updated_at"]


def test_chat_turn_persists_session(client: TestClient, fake_agent,
                                    history_dir) -> None:
    """A completed exchange saves to history like legacy ui.py (parity)."""
    from seatunnel_agent.common import history

    resp = client.post("/api/seatunnel/chat", json={"message": "build a pipeline"})
    cid = _sse_events(resp)[0]["id"]

    session = history.load_session(cid)
    assert session is not None
    assert session.title.startswith("build a pipeline")
    assert session.chat_messages[0] == {"role": "user", "content": "build a pipeline"}
    contents = [m["content"] for m in session.chat_messages]
    assert "Hello" in contents  # the final text event, legacy-rendered
    # a second turn extends the same session file
    client.post("/api/seatunnel/chat",
                json={"message": "more", "conversation_id": cid})
    session = history.load_session(cid)
    assert [m for m in session.chat_messages if m["role"] == "user"] == [
        {"role": "user", "content": "build a pipeline"},
        {"role": "user", "content": "more"},
    ]
    assert session.created_at  # preserved across saves


def test_session_load_returns_messages(client: TestClient, history_dir) -> None:
    _write_session("abc123")
    resp = client.get("/api/seatunnel/sessions/abc123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc123"
    assert data["title"] == "Old chat"
    assert data["messages"] == [
        {"role": "user", "content": "restore me"},
        {"role": "assistant", "content": "restored reply"},
    ]


def test_session_load_unknown_404(client: TestClient, history_dir) -> None:
    assert client.get("/api/seatunnel/sessions/nope").status_code == 404


def test_session_load_restores_agent_for_continuation(
    client: TestClient, fake_agent, history_dir,
) -> None:
    """After loading, a chat turn continues the restored conversation."""
    from seatunnel_agent.agents.data.seatunnel import api
    from seatunnel_agent.common import settings_store

    api.CONNECTION.update({"settings": object(),
                           "version": settings_store.get_version()})
    _write_session("abc123")
    assert client.get("/api/seatunnel/sessions/abc123").status_code == 200

    resp = client.post("/api/seatunnel/chat",
                       json={"message": "continue", "conversation_id": "abc123"})
    events = _sse_events(resp)
    assert events[0]["id"] == "abc123"
    # restored agent got the history and the follow-up went through chat()
    assert len(fake_agent.instances) == 1
    agent = fake_agent.instances[0]
    assert agent.chat_calls == ["continue"]
    assert agent.messages[0] == {"role": "user", "content": "restore me"}
    assert agent.context == {"k": "v"}

    # the continued exchange persisted onto the same session
    from seatunnel_agent.common import history

    session = history.load_session("abc123")
    assert {"role": "user", "content": "continue"} in session.chat_messages
    assert session.created_at == "2026-01-01T00:00:00"


def test_session_rename_roundtrip(client: TestClient, history_dir) -> None:
    from seatunnel_agent.common import history

    _write_session("abc123")
    resp = client.patch("/api/seatunnel/sessions/abc123",
                        json={"title": "Renamed"})
    assert resp.status_code == 200
    assert history.load_session("abc123").title == "Renamed"
    listed = client.get("/api/seatunnel/sessions").json()["sessions"]
    assert listed[0]["title"] == "Renamed"


def test_session_rename_unknown_404(client: TestClient, history_dir) -> None:
    resp = client.patch("/api/seatunnel/sessions/nope", json={"title": "x"})
    assert resp.status_code == 404


def test_session_delete(client: TestClient, fake_agent, history_dir) -> None:
    from seatunnel_agent.agents.data.seatunnel import api
    from seatunnel_agent.common import history

    _write_session("abc123")
    api._CONVERSATIONS["abc123"] = api._Conversation()
    resp = client.delete("/api/seatunnel/sessions/abc123")
    assert resp.status_code == 200
    assert history.load_session("abc123") is None
    assert "abc123" not in api._CONVERSATIONS
    assert client.get("/api/seatunnel/sessions").json()["sessions"] == []

# ── Upload ───────────────────────────────────────────────────────────


def test_upload_saves_file_and_returns_config_path(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uploaded file lands in configs/ with a sanitized name (legacy parity)."""
    monkeypatch.chdir(tmp_path)
    resp = client.post(
        "/api/seatunnel/upload",
        files={"file": ("my pipe#line.conf", b"env { }\n", "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == str(Path("configs") / "my_pipe_line.conf")
    saved = tmp_path / "configs" / "my_pipe_line.conf"
    assert saved.read_bytes() == b"env { }\n"


def test_upload_requires_file_part(client: TestClient) -> None:
    resp = client.post("/api/seatunnel/upload")
    assert resp.status_code == 422


def test_upload_rejects_oversized_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uploads over the 1 MB cap are rejected with 413 and nothing is saved."""
    monkeypatch.chdir(tmp_path)
    big = b"x" * (1024 * 1024 + 1)
    resp = client.post(
        "/api/seatunnel/upload",
        files={"file": ("huge.conf", big, "text/plain")},
    )
    assert resp.status_code == 413
    assert not (tmp_path / "configs" / "huge.conf").exists()


# ── Demo ─────────────────────────────────────────────────────────────


def test_demo_streams_general_script(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No config path -> 'general' script streamed over the chat SSE frames."""
    monkeypatch.setenv("UI_DEMO_STEP_DELAY", "0")
    resp = client.post("/api/seatunnel/demo", json={"config_path": "", "lang": "en"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(resp)
    assert events[0]["type"] == "conversation"
    kinds = [e["kind"] for e in events if e["type"] == "event"]
    # legacy _DEMO_STEPS["general"] order; final_answer becomes the final frame
    assert kinds == [
        "thinking", "tool_call", "tool_result",
        "thinking", "tool_call", "tool_result",
        "tool_call", "tool_result", "text",
    ]
    assert events[-1]["type"] == "final"
    assert "elapsed" in events[-1]

    # real execute_tool ran: list_connectors result rendered as markdown
    mds = [e["markdown"] for e in events if e["type"] == "event"]
    assert any("list_connectors" in m for m in mds)
    # text step carries the localized completion message with the demo path
    text_md = next(
        e["markdown"] for e in events if e["type"] == "event" and e["kind"] == "text"
    )
    assert "demo_fake_to_console.conf" in text_md


def test_demo_streams_validate_script_for_existing_config(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UI_DEMO_STEP_DELAY", "0")
    monkeypatch.chdir(tmp_path)
    from seatunnel_agent.agents.data.seatunnel.rendering import DEMO_CONFIG

    cfg = tmp_path / "pipe.conf"
    cfg.write_text(DEMO_CONFIG, encoding="utf-8")
    resp = client.post(
        "/api/seatunnel/demo", json={"config_path": str(cfg), "lang": "zh"}
    )
    assert resp.status_code == 200
    events = _sse_events(resp)
    kinds = [e["kind"] for e in events if e["type"] == "event"]
    assert kinds == [
        "thinking", "tool_call", "tool_result",
        "thinking", "tool_call", "tool_result", "text",
    ]
    text_md = next(
        e["markdown"] for e in events if e["type"] == "event" and e["kind"] == "text"
    )
    assert "验证完成" in text_md
    assert str(cfg) in text_md


def test_demo_general_writes_config_inside_cwd(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The demo's write_config call really writes, to a dir-guard-allowed path.

    Regression: the demo used to pre-write the config out-of-band to the OS
    temp dir, then script a write_config call that the dir guard refused —
    the transcript showed a failure while the summary claimed success.
    """
    monkeypatch.setenv("UI_DEMO_STEP_DELAY", "0")
    monkeypatch.chdir(tmp_path)
    resp = client.post("/api/seatunnel/demo", json={"config_path": "", "lang": "en"})
    assert resp.status_code == 200
    events = _sse_events(resp)
    mds = [e["markdown"] for e in events if e["type"] == "event"]

    # the scripted write_config call must not be refused by the dir guard
    assert not any("Refusing to operate" in m for m in mds)
    # the file really exists under the working directory
    assert (tmp_path / "configs" / "demo_fake_to_console.conf").is_file()
    text_md = next(
        e["markdown"] for e in events if e["type"] == "event" and e["kind"] == "text"
    )
    assert "demo_fake_to_console.conf" in text_md
    assert "Config generated and validated" in text_md


def test_demo_general_admits_write_failure(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a demo tool call fails, the summary says so instead of claiming success."""
    monkeypatch.setenv("UI_DEMO_STEP_DELAY", "0")
    monkeypatch.chdir(tmp_path)
    from seatunnel_agent.agents.data.seatunnel import tools as st_tools

    real_execute = st_tools.execute_tool

    def failing_execute(name, tool_input, settings):
        if name == "write_config":
            return '{"error": "disk on fire"}'
        return real_execute(name, tool_input, settings)

    monkeypatch.setattr(st_tools, "execute_tool", failing_execute)
    resp = client.post("/api/seatunnel/demo", json={"config_path": "", "lang": "en"})
    assert resp.status_code == 200
    events = _sse_events(resp)
    text_md = next(
        e["markdown"] for e in events if e["type"] == "event" and e["kind"] == "text"
    )
    assert "Config generated and validated" not in text_md
    assert "disk on fire" in text_md


def test_demo_honours_step_delay_env_var(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UI_DEMO_STEP_DELAY paces the stream (legacy ui.py:36 behaviour kept)."""
    import time as _time

    monkeypatch.setenv("UI_DEMO_STEP_DELAY", "0.05")
    t0 = _time.time()
    resp = client.post("/api/seatunnel/demo", json={"config_path": "", "lang": "en"})
    assert resp.status_code == 200
    _sse_events(resp)
    # 10 steps x 0.05s >= 0.5s lower bound
    assert _time.time() - t0 >= 0.5


# ── Export (legacy ui.py _export_session parity) ─────────────────────


def _read_zip(resp) -> zipfile.ZipFile:
    import io

    return zipfile.ZipFile(io.BytesIO(resp.content))


def test_export_in_memory_conversation_returns_zip(
    client: TestClient, fake_agent,
) -> None:
    from seatunnel_agent.agents.data.seatunnel import api

    first = _sse_events(client.post("/api/seatunnel/chat", json={"message": "hi"}))
    cid = first[0]["id"]
    assert api._CONVERSATIONS[cid].messages  # precondition: chat is recorded

    resp = client.get(f"/api/seatunnel/sessions/{cid}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    disp = resp.headers["content-disposition"]
    assert "attachment" in disp
    assert f"seatunnel_session_{cid}_" in disp
    assert ".zip" in disp

    zf = _read_zip(resp)
    assert zf.testzip() is None  # well-formed archive
    report = zf.read("report.md").decode("utf-8")
    assert "# SeaTunnel Agent Session Report" in report
    assert f"- **Session ID**: {cid}" in report
    assert "## User\n\nhi" in report
    assert "## Assistant" in report


def test_export_persisted_session_returns_zip(
    client: TestClient, history_dir,
) -> None:
    _write_session("abc123")
    resp = client.get("/api/seatunnel/sessions/abc123/export")
    assert resp.status_code == 200
    report = _read_zip(resp).read("report.md").decode("utf-8")
    assert "restore me" in report
    assert "restored reply" in report


def test_export_includes_created_config_files(
    client: TestClient, fake_agent, tmp_path,
) -> None:
    from seatunnel_agent.agents.data.seatunnel import api

    first = _sse_events(client.post("/api/seatunnel/chat", json={"message": "hi"}))
    cid = first[0]["id"]
    cfg = tmp_path / "job.conf"
    cfg.write_text("env {}\n", encoding="utf-8")
    api._CONVERSATIONS[cid].agent.context = {"created_configs": [str(cfg)]}

    zf = _read_zip(client.get(f"/api/seatunnel/sessions/{cid}/export"))
    assert "configs/job.conf" in zf.namelist()
    assert zf.read("configs/job.conf").decode("utf-8").strip() == "env {}"
    assert "## Generated Config Files" in zf.read("report.md").decode("utf-8")


def test_export_unknown_session_404(client: TestClient) -> None:
    assert client.get("/api/seatunnel/sessions/nope/export").status_code == 404


def test_export_empty_conversation_404(client: TestClient) -> None:
    from seatunnel_agent.agents.data.seatunnel import api

    api._CONVERSATIONS.clear()
    api._CONVERSATIONS["emptyc"] = api._Conversation()
    assert client.get("/api/seatunnel/sessions/emptyc/export").status_code == 404
