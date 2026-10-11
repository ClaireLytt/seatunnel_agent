# -*- coding: utf-8 -*-
"""Issue-triage agent: tools, JSON parsing, loop with FakeLLM, CLI, API."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config import Settings
from seatunnel_agent.issue_triage import (
    build_tools,
    load_issues,
    render_markdown,
    triage,
)
from seatunnel_agent.llm import LLMResponse, ToolCall

DEMO = Path(__file__).resolve().parents[1] / "examples" / "triage_demo"
SETTINGS = Settings(api_key="sk-test")


def _text(reply):
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"f": 1}, usage={})


def _tool(name, inp, cid="c1"):
    return LLMResponse(wants_tool_use=True,
                       tool_calls=[ToolCall(id=cid, name=name, input=inp)],
                       thinking_text="", reply_text="",
                       raw_content={"f": 1}, usage={})


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.tool_outputs = []

    def chat(self, system, messages):
        return self.responses.pop(0) if self.responses else _text("{}")

    def append_assistant(self, raw):
        return {"role": "assistant", "content": raw}

    def build_tool_result_message(self, trs):
        self.tool_outputs.extend(t["content"] for t in trs)
        return {"role": "user", "content": trs}


_FINAL = json.dumps({
    "labels": ["bug", "not-a-real-label"],
    "duplicates": ["#12", 23, "abc"],
    "priority": "HIGH",
    "reply": "感谢反馈,这看起来和 #12 是同一问题。",
}, ensure_ascii=False)


class TestTools:
    def test_search_similar_finds_dup(self):
        tools = {t.name: t for t in
                 build_tools(load_issues(DEMO / "issues.jsonl"), None)}
        out = tools["search_similar"].run(query="UI cannot start, port in use")
        assert "#12" in out

    def test_search_code_no_repo(self):
        tools = {t.name: t for t in build_tools([], None)}
        assert "no repository" in tools["search_code"].run(pattern="x")

    def test_search_code_real_repo(self):
        tools = {t.name: t for t in build_tools([], ".")}
        out = tools["search_code"].run(pattern="ToolLoopAgent")
        assert "agent_core" in out

    def test_search_docs(self):
        tools = {t.name: t for t in build_tools([], None)}
        assert "connector" in tools["search_docs"].run(query="Jdbc url").lower()


class TestTriage:
    def test_loop_and_parsing(self):
        client = ScriptedClient([
            _tool("search_similar", {"query": "ui port"}),
            _text(_FINAL),
        ])
        issues = load_issues(DEMO / "issues.jsonl")
        result = triage("UI 起不来", "端口被占用", SETTINGS, issues=issues,
                        repo_dir=None, client=client)
        assert result.parsed
        assert result.labels == ["bug"]              # unknown label dropped
        assert result.duplicates == [12, 23]         # "#12" ok, "abc" dropped
        assert result.priority == "high"             # normalized
        assert "同一问题" in result.draft
        assert "#12" in client.tool_outputs[0]       # tool actually ran
        md = render_markdown(result, "zh")
        assert "Issue 分诊" in md and "#12" in md

    def test_unparseable_reply_degrades(self):
        result = triage("t", "b", SETTINGS, issues=[], repo_dir=None,
                        client=ScriptedClient([_text("sorry, no json")]))
        assert not result.parsed
        assert "不是合法 JSON" in render_markdown(result, "zh")


class TestCliAndApi:
    def test_cli(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def fake_client(settings, tools=None, agent=None, **kw):
            return ScriptedClient([_text(_FINAL)])
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", fake_client)
        r = CliRunner().invoke(cli, ["triage", "-t", "UI 起不来",
                                     "-b", "端口占用", "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["labels"] == ["bug"]

    def test_api_no_key_503(self, monkeypatch):
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr("seatunnel_agent.settings_store.apply_to_env",
                            lambda: None)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.issue_triage.api import router
        app = FastAPI()
        app.include_router(router)
        resp = TestClient(app).post("/api/triage/run",
                                    json={"title": "x"})
        assert resp.status_code == 503

    def test_api_with_fake_llm(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def fake_client(settings, tools=None, agent=None, **kw):
            return ScriptedClient([_text(_FINAL)])
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", fake_client)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.issue_triage.api import router
        app = FastAPI()
        app.include_router(router)
        resp = TestClient(app).post("/api/triage/run", json={
            "title": "UI fails", "report": True, "lang": "en"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["priority"] == "high"
        assert "Issue Triage" in data["report"]

    def test_health(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.issue_triage.api import router
        app = FastAPI()
        app.include_router(router)
        assert TestClient(app).get("/api/triage/health").json() == {
            "status": "ok", "agent": "issue_triage"}
