"""Text2SQL history endpoints — ticket #69 seam (qlog + saved-session resume)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql import api as t2s_api
from seatunnel_agent.agents.data.text2sql.qlog import QueryLogger


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(t2s_api.router)
    return TestClient(app)


@pytest.fixture()
def qlog(tmp_path, monkeypatch) -> QueryLogger:
    logger = QueryLogger(log_dir=tmp_path)
    monkeypatch.setattr(t2s_api, "_query_logger", lambda: logger)
    logger.log("q1", "SELECT 1", "ok", exec_time_ms=10)
    logger.log("q2", "SELECT 2", "error", exec_time_ms=20)
    return logger


def test_qlog_list_newest_first(client, qlog):
    r = client.get("/api/text2sql/history/qlog?n=50")
    assert r.status_code == 200
    recs = r.json()["records"]
    assert [x["user_query"] for x in recs] == ["q2", "q1"]


def test_qlog_delete_by_newest_index(client, qlog):
    r = client.post("/api/text2sql/history/qlog/delete",
                    json={"indices": [0]})
    assert r.status_code == 200 and r.json()["deleted"] == 1
    recs = client.get("/api/text2sql/history/qlog").json()["records"]
    assert [x["user_query"] for x in recs] == ["q1"]


def test_qlog_clear_and_export(client, qlog):
    csv = client.get("/api/text2sql/history/qlog/export")
    assert csv.status_code == 200
    assert "q1" in csv.text and "SELECT 2" in csv.text
    assert csv.headers["content-type"].startswith("text/csv")
    r = client.post("/api/text2sql/history/qlog/clear")
    assert r.status_code == 200
    assert client.get("/api/text2sql/history/qlog").json()["records"] == []


def test_saved_sessions_list_and_resume(client, tmp_path, monkeypatch):
    # saved chat sessions live in a temp store
    from seatunnel_agent.agents.data.text2sql import chat_history as ch
    monkeypatch.setattr(ch, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(
        ch, "_session_path",
        lambda sid: tmp_path / f"{sid}.json")
    ch._invalidate_sessions_cache()
    saved = ch.Text2SQLSession(
        session_id="old1", title="revenue digging",
        created_at="2026-10-17T00:00:00", updated_at="2026-10-17T00:00:00",
        chat_messages=[{"role": "user", "content": "how much?"},
                       {"role": "assistant", "content": "42"}],
        agent_messages=[{"role": "user", "content": "how much?"}],
    )
    ch.save_t2s_session(saved)

    r = client.get("/api/text2sql/history/sessions")
    assert r.status_code == 200
    assert any(s["id"] == "old1" for s in r.json()["sessions"])

    # resume needs a live connected session
    db = tmp_path / "d.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (id INTEGER)")
    con.commit()
    con.close()
    live = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite", "db_config": {"database": str(db)},
    }).json()["session_id"]

    rr = client.post(f"/api/text2sql/session/{live}/resume",
                     json={"saved_id": "old1"})
    assert rr.status_code == 200
    chat = rr.json()["chat"]
    assert chat[0]["content"] == "how much?"
    # the live agent carries the restored conversation
    entry = t2s_api._sessions.get(live)
    assert entry.agent.messages and \
        entry.agent.messages[0]["content"] == "how much?"

    assert client.post(f"/api/text2sql/session/{live}/resume",
                       json={"saved_id": "ghost"}).status_code == 404
    assert client.post("/api/text2sql/session/nope/resume",
                       json={"saved_id": "old1"}).status_code == 404
