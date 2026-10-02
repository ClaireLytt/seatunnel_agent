# -*- coding: utf-8 -*-
"""Orchestrator: catalog, tool-use loop, keyword router, CLI, API.

Fully offline — the LLM is a scripted fake injected as ``client``.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMResponse, ToolCall
from seatunnel_agent.orchestrator import (
    Orchestrator,
    build_catalog,
    render_markdown,
    render_suggestions,
    suggest,
    tool_definitions,
)

SETTINGS = Settings(api_key="sk-test")


@pytest.fixture(autouse=True)
def _tmp_audit(monkeypatch, tmp_path):
    """Toolbox calls are audited — keep that JSONL out of the repo."""
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH",
                       str(tmp_path / "audit.jsonl"))


def _text(reply: str) -> LLMResponse:
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"fake": True},
                       usage={"input_tokens": 5, "output_tokens": 5})


def _tool(name: str, tool_input: dict, call_id: str = "t1") -> LLMResponse:
    return LLMResponse(
        wants_tool_use=True,
        tool_calls=[ToolCall(id=call_id, name=name, input=tool_input)],
        thinking_text="", reply_text="", raw_content={"fake": True},
        usage={"input_tokens": 5, "output_tokens": 5})


class ScriptedClient:
    """Plays back a list of LLMResponses; records the message history."""

    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)
        self.tool_results: list = []

    def chat(self, system: str, messages: list) -> LLMResponse:
        if not self.responses:
            return _text("out of script")
        return self.responses.pop(0)

    def append_assistant(self, raw) -> dict:
        return {"role": "assistant", "content": raw}

    def build_tool_result_message(self, tool_results: list) -> dict:
        self.tool_results.extend(tool_results)
        return {"role": "user", "content": tool_results}


class TestCatalog:
    def test_expected_agents_present(self):
        catalog = build_catalog()
        for name in ("sql_review", "sql_transpile", "impact_diff",
                     "migrate_to_seatunnel", "skew_check", "sql_fmt",
                     "config_lint", "schema_drift", "pii_scan",
                     "sql_testgen"):
            assert name in catalog, name
        assert "skew_check_file" not in catalog  # file tools stay out

    def test_specs_have_schema_desc_and_run(self):
        for name, spec in build_catalog().items():
            assert spec.description, name
            assert callable(spec.run), name
            schema = spec.input_schema
            assert schema["type"] == "object", name
            assert schema["properties"], name
            for req in schema["required"]:
                assert req in schema["properties"], name

    def test_tool_definitions_shape(self):
        defs = tool_definitions(build_catalog())
        assert all(set(d) == {"name", "description", "input_schema"}
                   for d in defs)

    @pytest.mark.parametrize("name,kwargs,expect", [
        ("sql_fmt", {"sql": "select 1"}, "SELECT"),
        ("config_lint", {"config": "env { job.mode = BATCH }\n"
                                   "source { FakeSource { } }\n"
                                   "sink { Console { } }"}, ""),
        ("schema_drift", {"old_ddl": "CREATE TABLE t (a INT)",
                          "new_ddl": "CREATE TABLE t (a BIGINT)"}, "t"),
        ("pii_scan", {"sql": "CREATE TABLE u (phone STRING COMMENT '手机号')"},
         "phone"),
        ("sql_testgen", {"sql": "SELECT id FROM t WHERE id > 5", "rows": 3},
         "t"),
        ("sql_review", {"sql": "SELECT * FROM a, b"}, ""),
    ])
    def test_wrappers_return_markdown(self, name, kwargs, expect):
        spec = build_catalog()[name]
        out = spec.run(**kwargs)
        assert isinstance(out, str) and out.strip()
        assert expect.lower() in out.lower()

    def test_wrappers_reject_empty_input(self):
        catalog = build_catalog()
        assert "不能为空" in catalog["sql_fmt"].run(sql="  ")
        assert "不能为空" in catalog["config_lint"].run(config="")


class TestEngine:
    def test_tool_then_answer(self):
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "select 1"}),
            _text("formatted, here you go"),
        ])
        result = Orchestrator(SETTINGS, client=client).run("format: select 1")
        assert result.reply == "formatted, here you go"
        assert [s.tool for s in result.steps] == ["sql_fmt"]
        assert not result.steps[0].error
        assert "SELECT" in client.tool_results[0]["content"]
        assert not result.truncated

    def test_chained_tools(self):
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "select 1"}, "c1"),
            _tool("sql_review", {"sql": "SELECT 1"}, "c2"),
            _text("done"),
        ])
        result = Orchestrator(SETTINGS, client=client).run("fmt then review")
        assert [s.tool for s in result.steps] == ["sql_fmt", "sql_review"]
        assert result.reply == "done"

    def test_tool_error_becomes_result(self):
        client = ScriptedClient([
            _tool("nope_tool", {"x": 1}),
            _text("sorry"),
        ])
        result = Orchestrator(SETTINGS, client=client).run("hi")
        assert result.steps[0].error
        assert "unknown tool" in result.steps[0].output

    def test_wrapper_exception_isolated(self):
        catalog = build_catalog()

        def boom(**kwargs):
            raise RuntimeError("kaput")
        catalog["sql_fmt"].run = boom
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "x"}),
            _text("recovered"),
        ])
        result = Orchestrator(SETTINGS, client=client,
                              catalog=catalog).run("hi")
        assert result.steps[0].error and "kaput" in result.steps[0].output
        assert result.reply == "recovered"

    def test_max_steps_forces_summary(self):
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "select 1"}, f"c{i}")
            for i in range(3)
        ] + [_text("partial summary")])
        result = Orchestrator(SETTINGS, client=client,
                              max_steps=3).run("loop forever")
        assert result.truncated
        assert result.reply == "partial summary"
        assert len(result.steps) == 3

    def test_forced_summary_with_tool_use_keeps_history_valid(self):
        # the model ignores the stop order at the step limit: its tool calls
        # must still get tool_results, and the reply must not be empty
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "select 1"}, "c0"),
            _tool("sql_fmt", {"sql": "select 1"}, "c1"),  # forced-summary turn
        ])
        orch = Orchestrator(SETTINGS, client=client, max_steps=1)
        result = orch.run("loop")
        assert result.truncated
        assert result.reply  # bilingual fallback, never empty
        answered = {tr["tool_use_id"] for tr in client.tool_results}
        assert {"c0", "c1"} <= answered  # every tool_use has a tool_result

    def test_plain_answer_no_tools(self):
        client = ScriptedClient([_text("lineage is …")])
        result = Orchestrator(SETTINGS, client=client).run("什么是血缘?")
        assert result.steps == []
        assert result.reply == "lineage is …"

    def test_multi_turn_history_kept(self):
        client = ScriptedClient([_text("one"), _text("two")])
        orch = Orchestrator(SETTINGS, client=client)
        orch.run("first")
        orch.run("second")
        users = [m for m in orch.messages if m.get("role") == "user"]
        assert len(users) == 2

    def test_empty_request_raises(self):
        with pytest.raises(ValueError):
            Orchestrator(SETTINGS, client=ScriptedClient([])).run("  ")


class TestRouter:
    def test_suggest_matches_keywords(self):
        catalog = build_catalog()
        hits = suggest("帮我审查这段 SQL 的性能问题", catalog)
        assert hits and hits[0].tool == "sql_review"
        hits = suggest("translate to doris and check skew", catalog)
        assert {h.tool for h in hits} >= {"sql_transpile", "skew_check"}

    def test_suggest_no_match(self):
        assert suggest("hello world", build_catalog()) == []

    def test_ascii_keywords_respect_word_boundaries(self):
        # "cr" must not fire inside "create"/"script"
        catalog = build_catalog()
        hits = suggest("create table users (id int)", catalog)
        assert all(h.tool != "sql_review" for h in hits)
        assert any(h.tool == "sql_review" for h in suggest("帮我做个 CR", catalog))

    def test_render_suggestions_bilingual(self):
        catalog = build_catalog()
        md = render_suggestions(suggest("审查 sql", catalog), "zh")
        assert "sql_review" in md and "/sqlreview" in md
        empty = render_suggestions([], "en")
        assert "No LLM configured" in empty


class TestReport:
    def test_markdown(self):
        client = ScriptedClient([
            _tool("sql_fmt", {"sql": "select 1"}),
            _text("done"),
        ])
        result = Orchestrator(SETTINGS, client=client).run("x")
        zh = render_markdown(result, "zh")
        assert "工具调用" in zh and "sql_fmt" in zh and "done" in zh
        en = render_markdown(result, "en")
        assert "Tool steps" in en


class TestCli:
    def test_no_key_prints_suggestions_exit_0(self, monkeypatch):
        # a developer machine has a real .env and saved UI settings — both
        # must stay out of this test (and no network call may ever happen)
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr("seatunnel_agent.settings_store.apply_to_env",
                            lambda: None)
        r = CliRunner().invoke(cli, ["orchestrate", "审查这段 sql"])
        assert r.exit_code == 0, r.output
        assert "sql_review" in r.output

    def test_with_fake_llm(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def fake_client(settings, tools=None, **kw):
            return ScriptedClient([
                _tool("sql_fmt", {"sql": "select 1"}),
                _text("all done"),
            ])
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", fake_client)
        r = CliRunner().invoke(cli, ["orchestrate", "format my sql",
                                     "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["reply"] == "all done"
        assert payload["steps"][0]["tool"] == "sql_fmt"


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.orchestrator.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_agents_endpoint(self):
        resp = self._client().get("/api/orchestrator/agents")
        assert resp.status_code == 200
        names = {a["name"] for a in resp.json()["agents"]}
        assert "sql_review" in names and "sql_fmt" in names

    def test_run_no_key_suggests(self, monkeypatch):
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr("seatunnel_agent.settings_store.apply_to_env",
                            lambda: None)
        resp = self._client().post("/api/orchestrator/run",
                                   json={"request": "审查 sql", "lang": "zh"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggested_only"] is True
        assert "sql_review" in data["reply"]

    def test_run_with_fake_llm(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def fake_client(settings, tools=None, **kw):
            return ScriptedClient([
                _tool("sql_fmt", {"sql": "select 1"}),
                _text("finished"),
            ])
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", fake_client)
        resp = self._client().post("/api/orchestrator/run",
                                   json={"request": "format it"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "finished"
        assert data["steps"][0]["tool"] == "sql_fmt"
        assert data["suggested_only"] is False

    def test_provider_failure_maps_to_503(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test")

        def broken_client(settings, tools=None, **kw):
            class Boom:
                def chat(self, *a, **k):
                    raise RuntimeError("auth failed")
                def append_assistant(self, raw):
                    return {"role": "assistant", "content": raw}
                def build_tool_result_message(self, trs):
                    return {"role": "user", "content": trs}
            return Boom()
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", broken_client)
        resp = self._client().post("/api/orchestrator/run",
                                   json={"request": "hi"})
        assert resp.status_code == 503
        assert "auth failed" in resp.json()["detail"]

    def test_health(self):
        resp = self._client().get("/api/orchestrator/health")
        assert resp.json() == {"status": "ok", "agent": "orchestrator"}
