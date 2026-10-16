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
    assert events[0]["type"] == "text"
    assert events[-1]["type"] == "final"
    assert events[-1].get("stopped") is True


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
