# -*- coding: utf-8 -*-
"""LLM eval harness: suite parsing, checkers, runner, regression, CLI, API.

Fully offline — the LLM is a scripted fake injected via client_factory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMResponse
from seatunnel_agent.llm_eval import (
    RunLogger,
    compare,
    load_suite,
    parse_suite,
    render_markdown,
    run_check,
    run_suite,
)
from seatunnel_agent.llm_eval.scoring import extract_sql
from seatunnel_agent.llm_eval.suite import Check

DEMO = Path(__file__).resolve().parents[1] / "examples" / "llmeval_demo"
SETTINGS = Settings(api_key="sk-test")


class FakeClient:
    """Scripted replies keyed by a substring of the user message."""

    def __init__(self, settings: Settings, script: dict[str, str] | None = None,
                 default: str = "SELECT 1"):
        self.settings = settings
        self.script = script or {}
        self.default = default

    def chat(self, system: str, messages: list[dict]) -> LLMResponse:
        user = messages[-1]["content"]
        reply = next((v for k, v in self.script.items() if k in user),
                     self.default)
        return LLMResponse(wants_tool_use=False, tool_calls=[],
                           thinking_text="", reply_text=reply,
                           raw_content=None,
                           usage={"input_tokens": 7, "output_tokens": 3})


def factory(script: dict[str, str] | None = None, default: str = "SELECT 1"):
    return lambda settings, **kw: FakeClient(settings, script, default)


_MINI_SUITE = """
suite: mini
cases:
  - id: a
    agent: raw_prompt
    input: {prompt: "say hello"}
    expect:
      - {type: icontains, value: "hello"}
  - id: b
    agent: raw_prompt
    weight: 3
    input: {prompt: "write sql"}
    expect:
      - {type: sql_valid, dialect: hive}
      - {type: not_contains, value: "DROP"}
"""


class TestSuiteParsing:
    def test_demo_suites_parse(self):
        for name in ("text2sql_golden.yaml", "sql_review_golden.yaml"):
            suite = load_suite(DEMO / name)
            assert suite.cases

    def test_valid_mini(self):
        suite = parse_suite(_MINI_SUITE)
        assert suite.name == "mini"
        assert suite.cases[1].weight == 3

    @pytest.mark.parametrize("bad,msg", [
        ("cases: 42", "期望顶层"),
        ("cases:\n  - hello", "必须是对象"),
        ("cases:\n  - {id: x, agent: nope, input: {p: 1}, expect: [{type: contains, value: y}]}",
         "未知 agent"),
        ("cases:\n  - {id: x, agent: raw_prompt, input: {}, expect: [{type: contains, value: y}]}",
         "input"),
        ("cases:\n  - {id: x, agent: raw_prompt, input: {p: 1}, expect: []}",
         "expect"),
        ("cases:\n  - {id: x, agent: raw_prompt, input: {p: 1}, expect: [{type: wat, value: y}]}",
         "未知检查类型"),
        ("cases:\n  - {id: x, agent: raw_prompt, input: {p: 1}, expect: [{type: contains}]}",
         "缺少 value"),
        ("cases:\n  - {id: x, agent: raw_prompt, input: {p: 1}, expect: [{type: contains, value: y}], weight: 0}",
         "weight"),
    ])
    def test_invalid_suites_cite_case(self, bad, msg):
        with pytest.raises(ValueError, match=msg):
            parse_suite(bad)

    def test_duplicate_ids(self):
        dup = """
cases:
  - {id: x, agent: raw_prompt, input: {p: 1}, expect: [{type: contains, value: y}]}
  - {id: x, agent: raw_prompt, input: {p: 1}, expect: [{type: contains, value: y}]}
"""
        with pytest.raises(ValueError, match="重复"):
            parse_suite(dup)


class TestCheckers:
    @pytest.mark.parametrize("ctype,value,output,ok", [
        ("contains", "GROUP BY", "… GROUP BY city", True),
        ("contains", "GROUP BY", "group by city", False),
        ("icontains", "GROUP BY", "group by city", True),
        ("not_contains", "DROP", "SELECT 1", True),
        ("not_contains", "DROP", "DROP TABLE t", False),
        ("regex", r"(?i)limit\s+10", "… LIMIT 10", True),
        ("regex", r"limit\s+10", "LIMIT 99", False),
        ("equals", "ok", "  ok  ", True),
        ("equals", "ok", "ok!", False),
        ("json_valid", "", '{"a": 1}', True),
        ("json_valid", "", "not json", False),
        ("json_valid", "", '```json\n{"a": 1}\n```', True),
        ("sql_valid", "", "SELECT 1", True),
        ("sql_valid", "", "SELEKT 1 FORM", False),
        ("sql_valid", "", "Here you go:\n```sql\nSELECT 1\n```", True),
    ])
    def test_run_check(self, ctype, value, output, ok):
        check = Check(type=ctype, value=value)
        passed, _ = run_check(check, output)
        assert passed is ok

    def test_bad_regex_fails_not_raises(self):
        passed, detail = run_check(Check(type="regex", value="("), "x")
        assert passed is False and "非法" in detail

    def test_extract_sql_joins_blocks(self):
        out = "```sql\nSELECT 1\n```\ntext\n```sql\nSELECT 2\n```"
        assert extract_sql(out) == "SELECT 1\nSELECT 2"


class TestRunner:
    def test_scores_and_weights(self):
        suite = parse_suite(_MINI_SUITE)
        result = run_suite(suite, settings=SETTINGS,
                           client_factory=factory({"say hello": "Hello!"}))
        a, b = result.cases
        assert a.passed and a.score == 1.0
        assert b.passed  # default "SELECT 1" parses and has no DROP
        assert result.score == 1.0
        assert a.usage["input_tokens"] == 7

    def test_failed_check_scores_fraction(self):
        suite = parse_suite(_MINI_SUITE)
        result = run_suite(
            suite, settings=SETTINGS,
            client_factory=factory({"say hello": "Hello!",
                                    "write sql": "DROP TABLE t"}))
        b = result.cases[1]
        assert not b.passed
        assert b.score == pytest.approx(0.5)  # sql_valid ok, not_contains fails
        # weighted: (1*1 + 0.5*3) / 4
        assert result.score == pytest.approx(0.625)

    def test_adapter_error_isolated(self):
        suite = parse_suite("""
cases:
  - {id: x, agent: raw_prompt, input: {prompt: ""}, expect: [{type: contains, value: y}]}
  - {id: ok, agent: raw_prompt, input: {prompt: "hi"}, expect: [{type: contains, value: "SELECT"}]}
""")
        result = run_suite(suite, settings=SETTINGS, client_factory=factory())
        assert result.cases[0].error  # empty prompt → adapter raises
        assert result.cases[0].score == 0.0
        assert result.cases[1].passed

    def test_judge_advisory_only(self):
        suite = parse_suite("""
cases:
  - id: j
    agent: raw_prompt
    input: {prompt: "hi"}
    expect:
      - {type: contains, value: "SELECT"}
      - {type: judge, value: "must be friendly"}
""")
        # judge off → check skipped entirely
        r1 = run_suite(suite, settings=SETTINGS, client_factory=factory())
        assert len(r1.cases[0].checks) == 1
        # judge on and failing → advisory, never gates pass/score
        r2 = run_suite(suite, settings=SETTINGS,
                       client_factory=factory(default="SELECT 1"),
                       judge=True)
        judge_checks = [c for c in r2.cases[0].checks if c.type == "judge"]
        assert judge_checks and judge_checks[0].advisory
        assert not judge_checks[0].passed  # "SELECT 1" ≠ PASS
        assert r2.cases[0].passed and r2.cases[0].score == 1.0

    def test_text2sql_and_sql_review_adapters(self):
        suite = parse_suite("""
cases:
  - id: t
    agent: text2sql
    input: {question: "各城市GMV", ddl: "CREATE TABLE t (city STRING)"}
    expect: [{type: sql_valid, dialect: hive}]
  - id: r
    agent: sql_review
    input: {sql: "SELECT 1", lang: zh}
    expect: [{type: contains, value: "SELECT"}]
""")
        fac = factory({"各城市GMV": "```sql\nSELECT city FROM t\n```",
                       "SELECT 1": "严重问题: 无 — SELECT 1 很干净"})
        result = run_suite(suite, settings=SETTINGS, client_factory=fac)
        assert all(c.passed for c in result.cases), [
            c.to_dict() for c in result.cases]


class TestRegression:
    @pytest.fixture()
    def eval_log(self, monkeypatch, tmp_path):
        log = tmp_path / "runs.jsonl"
        monkeypatch.setenv("LLM_EVAL_LOG", "1")
        monkeypatch.setenv("LLM_EVAL_PATH", str(log))
        return log

    def test_pass_to_fail_is_regression(self, eval_log):
        # baseline is fetched BEFORE each run (run_suite appends its own)
        suite = parse_suite(_MINI_SUITE)
        baseline = RunLogger().last_run("mini")
        good = run_suite(suite, settings=SETTINGS,
                         client_factory=factory({"say hello": "Hello!"}))
        assert compare(good, baseline)["has_baseline"] is False
        baseline = RunLogger().last_run("mini")
        bad = run_suite(suite, settings=SETTINGS,
                        client_factory=factory({"say hello": "Hi!"}))
        verdict = compare(bad, baseline)
        assert verdict["regressed"] is True
        assert verdict["regressed_cases"] == ["a"]

    def test_no_regression_when_stable(self, eval_log):
        suite = parse_suite(_MINI_SUITE)
        fac = factory({"say hello": "Hello!"})
        run_suite(suite, settings=SETTINGS, client_factory=fac)
        baseline = RunLogger().last_run("mini")
        again = run_suite(suite, settings=SETTINGS, client_factory=fac)
        verdict = compare(again, baseline)
        assert verdict == {"has_baseline": True, "regressed": False,
                           "regressed_cases": [], "score_drop": 0.0}

    def test_baseline_correct_with_logging_disabled(self, eval_log,
                                                    monkeypatch):
        # regression gate must work even when THIS run is not logged:
        # the baseline comes from before the run, never from runs[-2]
        suite = parse_suite(_MINI_SUITE)
        run_suite(suite, settings=SETTINGS,
                  client_factory=factory({"say hello": "Hello!"}))
        monkeypatch.setenv("LLM_EVAL_LOG", "0")
        baseline = RunLogger().last_run("mini")
        bad = run_suite(suite, settings=SETTINGS,
                        client_factory=factory({"say hello": "Hi!"}))
        verdict = compare(bad, baseline)
        assert verdict["regressed"] is True
        assert verdict["regressed_cases"] == ["a"]


class TestReport:
    def test_markdown_bilingual(self):
        suite = parse_suite(_MINI_SUITE)
        result = run_suite(suite, settings=SETTINGS,
                           client_factory=factory({"say hello": "nope"}))
        zh = render_markdown(result, "zh",
                             {"has_baseline": False, "regressed": False,
                              "regressed_cases": [], "score_drop": 0.0})
        assert "LLM 评测" in zh and "未通过的检查" in zh and "基线" in zh
        en = render_markdown(result, "en")
        assert "LLM Eval" in en and "Failed checks" in en


class TestCli:
    def _patch_llm(self, monkeypatch, script=None):
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient",
                            factory(script or {"say hello": "Hello!"}))
        monkeypatch.setenv("API_KEY", "sk-test")

    def _suite_file(self, tmp_path) -> str:
        p = tmp_path / "mini.yaml"
        p.write_text(_MINI_SUITE, encoding="utf-8")
        return str(p)

    def test_llmeval_pass(self, monkeypatch, tmp_path):
        self._patch_llm(monkeypatch)
        r = CliRunner().invoke(cli, ["llmeval", self._suite_file(tmp_path),
                                     "--fail-on", "fail"])
        assert r.exit_code == 0, r.output
        assert "LLM 评测" in r.output

    def test_llmeval_fail_gate(self, monkeypatch, tmp_path):
        self._patch_llm(monkeypatch, {"say hello": "nope"})
        r = CliRunner().invoke(cli, ["llmeval", self._suite_file(tmp_path),
                                     "--fail-on", "fail"])
        assert r.exit_code == 1

    def test_llmeval_regression_gate(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LLM_EVAL_LOG", "1")
        monkeypatch.setenv("LLM_EVAL_PATH", str(tmp_path / "runs.jsonl"))
        sf = self._suite_file(tmp_path)
        self._patch_llm(monkeypatch)
        assert CliRunner().invoke(
            cli, ["llmeval", sf, "--fail-on", "regression"]).exit_code == 0
        self._patch_llm(monkeypatch, {"say hello": "nope"})
        r = CliRunner().invoke(cli, ["llmeval", sf,
                                     "--fail-on", "regression"])
        assert r.exit_code == 1

    def test_llmeval_json(self, monkeypatch, tmp_path):
        self._patch_llm(monkeypatch)
        r = CliRunner().invoke(cli, ["llmeval", self._suite_file(tmp_path),
                                     "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["result"]["suite"] == "mini"

    def test_llmeval_no_key_readable_exit_2(self, monkeypatch, tmp_path):
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr("seatunnel_agent.settings_store.apply_to_env",
                            lambda: None)
        r = CliRunner().invoke(cli, ["llmeval", self._suite_file(tmp_path)])
        assert r.exit_code == 2
        assert "Traceback" not in r.output
        assert "API_KEY" in r.output

    def test_llmeval_bad_suite_exit_2(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("cases: 42", encoding="utf-8")
        r = CliRunner().invoke(cli, ["llmeval", str(bad)])
        assert r.exit_code == 2


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.llm_eval.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_run_endpoint(self, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient",
                            factory({"say hello": "Hello!"}))
        monkeypatch.setenv("API_KEY", "sk-test")
        resp = self._client().post("/api/llmeval/run", json={
            "suite_yaml": _MINI_SUITE, "lang": "en", "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["score"] == 1.0
        assert "LLM Eval" in data["report"]

    def test_run_bad_suite_400(self):
        resp = self._client().post("/api/llmeval/run",
                                   json={"suite_yaml": "cases: 42"})
        assert resp.status_code == 400

    def test_health(self):
        resp = self._client().get("/api/llmeval/health")
        assert resp.json() == {"status": "ok", "agent": "llm_eval"}
