"""Text2SQL streaming chat endpoints — ticket #65 seam (SSE protocol).

The agent is faked: the seam under test is the event stream, the stop
switch, and the new-chat reset — never the LLM.
"""

from __future__ import annotations

import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql import api as t2s_api


class FakeAgent:
    """Emits text → execute_sql result → final, like a real turn."""

    def __init__(self) -> None:
        self._on_event = None
        self.runtime = type("R", (), {"ds_type": "sqlite"})()
        self.runtime.store = type("S", (), {"tables": []})()
        self.questions: list[str] = []

    def set_event_hook(self, cb):
        self._on_event = cb

    def chat(self, message: str) -> str:
        self.questions.append(message)
        self._on_event("text", {"text": "looking at orders"})
        self._on_event("tool_result", {
            "name": "execute_sql",
            "result": {"sql": "SELECT 1", "columns": ["n"], "rows": [[1]],
                       "row_count": 1},
        })
        self._on_event("final_answer", {"text": "there is 1 row"})
        return "there is 1 row"


class BlockingAgent(FakeAgent):
    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def set_event_hook(self, cb):
        self._on_event = cb

    def chat(self, message: str) -> str:
        self._on_event("text", {"text": "thinking…"})
        self.release.wait(timeout=30)
        return "late"


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(t2s_api.router)
    return TestClient(app)


def _connect_fake(client, monkeypatch, agent) -> str:
    monkeypatch.setattr(t2s_api, "_build_agent", lambda *a, **k: agent)
    r = client.post("/api/text2sql/connect",
                    json={"ds_type": "sqlite", "db_config": {"database": "x"}})
    assert r.status_code == 200
    return r.json()["session_id"]


def _read_events(resp) -> list[dict]:
    events = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_chat_streams_text_result_final(client, monkeypatch):
    sid = _connect_fake(client, monkeypatch, FakeAgent())
    with client.stream("POST", "/api/text2sql/chat",
                       json={"session_id": sid, "question": "how many?"}) as r:
        assert r.status_code == 200
        events = _read_events(r)
    kinds = [e["type"] for e in events]
    assert kinds == ["text", "result", "final"]
    assert events[1]["columns"] == ["n"]
    assert events[1]["rows"] == [[1]]
    assert events[1]["sql"] == "SELECT 1"
    assert events[2]["text"] == "there is 1 row"


class ChartAgent(FakeAgent):
    def set_event_hook(self, cb):
        self._on_event = cb

    def chat(self, message: str) -> str:
        self._on_event("tool_result", {
            "name": "execute_sql",
            "result": {"sql": "SELECT region, amount FROM t",
                       "columns": ["region", "amount"],
                       "rows": [["north", 10], ["south", 25], ["east", 7]],
                       "row_count": 3},
        })
        self._on_event("final_answer", {"text": "done"})
        return "done"


def test_result_event_carries_server_detected_chart_type(client, monkeypatch):
    sid = _connect_fake(client, monkeypatch, ChartAgent())
    with client.stream("POST", "/api/text2sql/chat",
                       json={"session_id": sid, "question": "q"}) as r:
        events = _read_events(r)
    result = next(e for e in events if e["type"] == "result")
    assert result["chart_type"] in ("bar", "line", "pie", "scatter")


def test_single_row_result_has_no_chart_type(client, monkeypatch):
    sid = _connect_fake(client, monkeypatch, FakeAgent())
    with client.stream("POST", "/api/text2sql/chat",
                       json={"session_id": sid, "question": "q"}) as r:
        events = _read_events(r)
    result = next(e for e in events if e["type"] == "result")
    assert result.get("chart_type") is None


class RealShapeAgent(FakeAgent):
    """Mimics the real agent: tool_result carries a JSON *string*, and the
    answer streams as text_delta chunks before the final message."""

    def set_event_hook(self, cb):
        self._on_event = cb

    def chat(self, message: str) -> str:
        self._on_event("text_delta", {"text": "there "})
        self._on_event("text_delta", {"text": "is 1 row"})
        self._on_event("tool_result", {
            "name": "execute_sql",
            "result": json.dumps({"sql": "SELECT 1", "columns": ["n"],
                                  "rows": [[1]], "row_count": 1}),
        })
        self._on_event("final_answer", {"text": "there is 1 row"})
        return "there is 1 row"


def test_string_tool_result_is_parsed_not_crashed(client, monkeypatch):
    sid = _connect_fake(client, monkeypatch, RealShapeAgent())
    with client.stream("POST", "/api/text2sql/chat",
                       json={"session_id": sid, "question": "q"}) as r:
        events = _read_events(r)
    kinds = [e["type"] for e in events]
    assert "result" in kinds and kinds[-1] == "final"
    result = next(e for e in events if e["type"] == "result")
    assert result["columns"] == ["n"] and result["rows"] == [[1]]


def test_text_deltas_stream_as_delta_events(client, monkeypatch):
    sid = _connect_fake(client, monkeypatch, RealShapeAgent())
    with client.stream("POST", "/api/text2sql/chat",
                       json={"session_id": sid, "question": "q"}) as r:
        events = _read_events(r)
    deltas = [e["text"] for e in events if e["type"] == "delta"]
    assert deltas == ["there ", "is 1 row"]


def test_concurrent_chat_on_same_session_409(client, monkeypatch):
    agent = BlockingAgent()
    sid = _connect_fake(client, monkeypatch, agent)
    def reader() -> None:
        with client.stream("POST", "/api/text2sql/chat",
                           json={"session_id": sid, "question": "q"}) as r:
            for _ in r.iter_lines():
                pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    # wait until the stream's worker hooked our fake (probing with POST /chat
    # would itself start a real turn and poison the session)
    import time
    deadline = time.time() + 10
    while agent._on_event is None and time.time() < deadline:
        time.sleep(0.05)
    assert agent._on_event is not None, "chat never started"
    r = client.post("/api/text2sql/chat",
                    json={"session_id": sid, "question": "again"})
    assert r.status_code == 409
    client.post("/api/text2sql/chat/stop", json={"session_id": sid})
    agent.release.set()
    t.join(timeout=10)
    assert not t.is_alive()


def test_chat_unknown_session_404(client):
    r = client.post("/api/text2sql/chat",
                    json={"session_id": "nope", "question": "hi"})
    assert r.status_code == 404


def test_stop_terminates_stream(client, monkeypatch):
    agent = BlockingAgent()
    sid = _connect_fake(client, monkeypatch, agent)

    events: list[dict] = []

    def reader() -> None:
        with client.stream("POST", "/api/text2sql/chat",
                           json={"session_id": sid, "question": "q"}) as r:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    # TestClient buffers SSE bodies, so "stream is live" is observed through
    # the stop endpoint itself: 404 until the chat registers, then 200.
    import time
    deadline = time.time() + 10
    stop_code = 404
    while stop_code == 404 and time.time() < deadline:
        stop_code = client.post("/api/text2sql/chat/stop",
                                json={"session_id": sid}).status_code
        if stop_code == 404:
            time.sleep(0.1)
    assert stop_code == 200, "chat never became active"
    t.join(timeout=10)
    agent.release.set()
    assert not t.is_alive(), "stream did not terminate on stop"
    # stop may legally preempt the worker's first event, so only the
    # terminal semantics are asserted
    assert events[-1]["type"] == "final"
    assert events[-1].get("stopped") is True
    assert all(e["type"] in ("text", "final") for e in events)


def test_reset_rebuilds_agent(client, monkeypatch):
    calls = []

    def fake_build(*a, **k):
        calls.append(a)
        return FakeAgent()

    monkeypatch.setattr(t2s_api, "_build_agent", fake_build)
    r = client.post("/api/text2sql/connect",
                    json={"ds_type": "sqlite", "db_config": {"database": "x"}})
    sid = r.json()["session_id"]
    assert len(calls) == 1

    r2 = client.post(f"/api/text2sql/session/{sid}/reset")
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid
    assert len(calls) == 2  # fresh agent from the stored connect params

    assert client.post("/api/text2sql/session/nope/reset").status_code == 404
