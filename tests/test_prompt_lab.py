# -*- coding: utf-8 -*-
"""Prompt Lab: profile→Settings mapping, matrix runner, diff, CLI, API.

Fully offline — every LLM path is injected with a fake client factory.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMResponse
from seatunnel_agent.prompt_lab import (
    ACTIVE,
    ExperimentLogger,
    render_diff,
    render_matrix_markdown,
    run_matrix,
    settings_from_profile,
)


def _resp(text: str, inp: int = 10, out: int = 5) -> LLMResponse:
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=text, raw_content=None,
                       usage={"input_tokens": inp, "output_tokens": out})


class FakeClient:
    """Reply is derived from the model name so cells are distinguishable."""

    def __init__(self, settings: Settings, fail_for: set[str] = frozenset(),
                 **_kw):
        self.settings = settings
        self.fail_for = fail_for

    def chat(self, system: str, messages: list[dict]) -> LLMResponse:
        if self.settings.model_name in self.fail_for:
            raise RuntimeError("boom")
        return _resp(f"reply from {self.settings.model_name}")


@pytest.fixture()
def profiles(monkeypatch):
    """Two fake stored profiles + an active env config."""
    store = {
        "kimi": {"LLM_PROVIDER": "openai", "API_KEY": "sk-kimi",
                 "MODEL_NAME": "moonshot-v1-8k", "TEMPERATURE": "0.3",
                 "MAX_TOKENS": "4000", "LLM_TIMEOUT": "60"},
        "claude": {"LLM_PROVIDER": "anthropic", "API_KEY": "sk-ant",
                   "MODEL_NAME": "claude-opus-5"},
    }
    monkeypatch.setattr("seatunnel_agent.prompt_lab.runner.load_profile",
                        lambda name: store.get(name, {}))
    monkeypatch.setenv("API_KEY", "sk-active")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL_NAME", "claude-sonnet-5")
    return store


class TestSettingsFromProfile:
    def test_mapping_and_coercion(self, profiles):
        s = settings_from_profile(profiles["kimi"])
        assert s.llm_provider == "openai"
        assert s.api_key == "sk-kimi"
        assert s.model_name == "moonshot-v1-8k"
        assert s.temperature == pytest.approx(0.3)
        assert s.max_tokens == 4000
        assert s.llm_timeout == 60

    def test_defaults_applied(self):
        s = settings_from_profile({"API_KEY": "k"})
        assert s.llm_provider == "anthropic"
        assert s.max_tokens == 16000

    def test_bad_number_raises(self):
        with pytest.raises(ValueError):
            settings_from_profile({"API_KEY": "k", "TEMPERATURE": "hot"})


class TestRunMatrix:
    def test_cells_keep_order_and_metrics(self, profiles):
        result = run_matrix("hi", profiles=["kimi", "claude"],
                            client_factory=FakeClient)
        assert [c.profile for c in result.cells] == ["kimi", "claude"]
        assert result.cells[0].reply == "reply from moonshot-v1-8k"
        assert result.cells[1].reply == "reply from claude-opus-5"
        assert result.cells[0].input_tokens == 10
        assert result.cells[0].latency_ms >= 0
        assert not result.all_failed

    def test_parallel_preserves_order(self, profiles):
        result = run_matrix("hi", profiles=["kimi", "claude", ACTIVE],
                            parallel=True, client_factory=FakeClient)
        assert [c.profile for c in result.cells] == ["kimi", "claude", ACTIVE]
        assert result.cells[2].model == "claude-sonnet-5"  # from env

    def test_error_isolated_per_cell(self, profiles):
        factory = lambda s: FakeClient(s, fail_for={"moonshot-v1-8k"})  # noqa: E731
        result = run_matrix("hi", profiles=["kimi", "claude"],
                            client_factory=factory)
        assert result.cells[0].error and "boom" in result.cells[0].error
        assert result.cells[1].error is None
        assert not result.all_failed

    def test_all_failed(self, profiles):
        factory = lambda s: FakeClient(  # noqa: E731
            s, fail_for={"moonshot-v1-8k", "claude-opus-5"})
        result = run_matrix("hi", profiles=["kimi", "claude"],
                            client_factory=factory)
        assert result.all_failed

    def test_unknown_profile_is_cell_error(self, profiles):
        result = run_matrix("hi", profiles=["nope"],
                            client_factory=FakeClient)
        assert "nope" in result.cells[0].error

    def test_empty_prompt_raises(self, profiles):
        with pytest.raises(ValueError):
            run_matrix("   ", profiles=["kimi"], client_factory=FakeClient)


class TestLogging:
    def test_experiment_logged_with_previews_only(self, profiles,
                                                  monkeypatch, tmp_path):
        log = tmp_path / "lab.jsonl"
        monkeypatch.setenv("PROMPT_LAB_LOG", "1")
        monkeypatch.setenv("PROMPT_LAB_PATH", str(log))
        run_matrix("secret prompt " + "x" * 500, profiles=["kimi"],
                   client_factory=FakeClient)
        recs = ExperimentLogger().recent(5)
        assert len(recs) == 1
        assert len(recs[0]["prompt_preview"]) <= 200
        cell = recs[0]["cells"][0]
        assert cell["profile"] == "kimi"
        assert "sk-kimi" not in json.dumps(recs)  # never any secret

    def test_log_disabled_by_default_fixture(self, profiles, tmp_path,
                                             monkeypatch):
        log = tmp_path / "lab.jsonl"
        monkeypatch.setenv("PROMPT_LAB_PATH", str(log))
        run_matrix("hi", profiles=["kimi"], client_factory=FakeClient)
        assert not log.exists()  # conftest sets PROMPT_LAB_LOG=0


class TestReport:
    def test_matrix_markdown(self, profiles):
        result = run_matrix("hi", profiles=["kimi", "claude"],
                            client_factory=FakeClient)
        zh = render_matrix_markdown(result, "zh")
        assert "Prompt 实验室" in zh and "moonshot-v1-8k" in zh
        en = render_matrix_markdown(result, "en")
        assert "Prompt Lab" in en and "Outputs" in en

    def test_diff(self, profiles):
        result = run_matrix("hi", profiles=["kimi", "claude"],
                            client_factory=FakeClient)
        d = render_diff(result.cells[0], result.cells[1], "en")
        assert "```diff" in d and "moonshot-v1-8k" in d
        same = render_diff(result.cells[0], result.cells[0], "zh")
        assert "完全相同" in same


class TestCli:
    def test_promptlab_cli(self, profiles, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", FakeClient)
        r = CliRunner().invoke(cli_entry(), [
            "promptlab", "hello", "-p", "kimi", "-p", "claude"])
        assert r.exit_code == 0, r.output
        assert "moonshot-v1-8k" in r.output

    def test_promptlab_all_failed_exit_1(self, profiles, monkeypatch):
        factory = lambda s: FakeClient(  # noqa: E731
            s, fail_for={"moonshot-v1-8k"})
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", factory)
        r = CliRunner().invoke(cli_entry(), ["promptlab", "x", "-p", "kimi"])
        assert r.exit_code == 1

    def test_json_format(self, profiles, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", FakeClient)
        r = CliRunner().invoke(cli_entry(), [
            "promptlab", "hello", "-p", "kimi", "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload[0]["profile"] == "kimi"


def cli_entry():
    from seatunnel_agent.cli import cli
    return cli


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.prompt_lab.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_profiles_names_only(self, profiles, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.prompt_lab.api.list_profiles",
                            lambda: ["kimi", "claude"])
        resp = self._client().get("/api/promptlab/profiles")
        data = resp.json()
        assert data == {"profiles": [ACTIVE, "kimi", "claude"]}
        assert "sk-" not in resp.text

    def test_run_endpoint(self, profiles, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.llm.LLMClient", FakeClient)
        resp = self._client().post("/api/promptlab/run", json={
            "prompt": "hello", "profiles": ["kimi"], "lang": "en",
            "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cells"][0]["model"] == "moonshot-v1-8k"
        assert data["all_failed"] is False
        assert "Prompt Lab" in data["report"]
        assert "sk-kimi" not in resp.text

    def test_health(self):
        resp = self._client().get("/api/promptlab/health")
        assert resp.json() == {"status": "ok", "agent": "prompt_lab"}
