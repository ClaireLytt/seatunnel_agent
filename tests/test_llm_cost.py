# -*- coding: utf-8 -*-
"""LLM cost observability: pricing, aggregation, CLI gate, API.

Fully offline — reads the committed demo fixture or tmp files only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.llm_cost import (
    builtin_prices,
    check_budget,
    cost_usd,
    load_override,
    merged_prices,
    price_for,
    render_markdown,
    summarize_cost,
)
from seatunnel_agent.llm_cost.aggregate import _find_anomalies

DEMO = Path(__file__).resolve().parents[1] / "examples" / "llmcost_demo"
USAGE = DEMO / "llm_usage_sample.jsonl"
PRICING = DEMO / "pricing.yaml"
# The fixture carries fixed 2026-09 dates; a huge window keeps tests stable.
DAYS = 36500


@pytest.fixture(autouse=True)
def _no_user_pricing(monkeypatch, tmp_path):
    """Never read the developer's real ~/.seatunnel-agent/pricing.yaml."""
    monkeypatch.setenv("SEATUNNEL_PRICING_PATH",
                       str(tmp_path / "absent-pricing.yaml"))


class TestPricing:
    def test_longest_prefix_wins(self):
        prices = builtin_prices()
        assert price_for("gpt-4o-mini-2024", prices).prefix == "gpt-4o-mini"
        assert price_for("gpt-4o-2024", prices).prefix == "gpt-4o"

    def test_case_insensitive_and_unknown(self):
        assert price_for("Claude-Opus-5") is not None
        assert price_for("totally-unknown-model") is None
        assert price_for("") is None

    def test_cost_math(self):
        prices = builtin_prices()
        # deepseek-chat: 0.27 in / 1.10 out per 1M
        c = cost_usd("deepseek-chat", 1_000_000, 1_000_000, prices)
        assert c == pytest.approx(0.27 + 1.10)
        assert cost_usd("unknown", 100, 100, prices) is None

    def test_yaml_override_beats_builtin(self):
        entries = merged_prices(PRICING)
        e = price_for("deepseek-chat", entries)
        assert e.source == "override"
        assert e.input_usd == pytest.approx(0.14)
        # new model gets priced too
        assert price_for("my-private-llm", entries) is not None

    def test_override_missing_file_is_empty(self, tmp_path):
        assert load_override(tmp_path / "nope.yaml") == []

    def test_override_malformed_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("prices: {not: a-list}", encoding="utf-8")
        with pytest.raises(ValueError):
            load_override(bad)
        bad.write_text("prices:\n  - input: 1\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_override(bad)


class TestAggregate:
    def test_summary_on_demo_fixture(self):
        s = summarize_cost(DAYS, usage_file=USAGE)
        assert s["total"]["calls"] == 112
        assert s["total"]["cost_usd"] > 0
        assert "my-private-llm" in s["unpriced_models"]
        assert s["total"]["unpriced_calls"] == 1
        # per-agent attribution with an unattributed bucket
        assert "text2sql" in s["by_agent"]
        assert "unattributed" in s["by_agent"]
        # spike day flagged
        assert any(a["day"] == "2026-09-29" for a in s["anomalies"])

    def test_pricing_override_changes_total(self):
        base = summarize_cost(DAYS, usage_file=USAGE)
        over = summarize_cost(DAYS, usage_file=USAGE,
                              pricing_override=PRICING)
        assert over["unpriced_models"] == []  # my-private-llm now priced
        assert over["total"]["cost_usd"] != base["total"]["cost_usd"]

    def test_missing_log_is_empty(self, tmp_path):
        s = summarize_cost(30, usage_file=tmp_path / "none.jsonl")
        assert s["total"]["calls"] == 0
        assert s["anomalies"] == []

    def test_anomaly_needs_history(self):
        # 2 prior days only → never flagged, whatever the spike
        costs = {"2026-01-01": 1.0, "2026-01-02": 1.0, "2026-01-03": 99.0}
        assert _find_anomalies(costs) == []
        # ≥3 prior days and >2× mean → flagged
        costs = {"2026-01-01": 1.0, "2026-01-02": 1.0, "2026-01-03": 1.0,
                 "2026-01-04": 2.5}
        hits = _find_anomalies(costs)
        assert [a["day"] for a in hits] == ["2026-01-04"]
        assert hits[0]["baseline_usd"] == pytest.approx(1.0)

    def test_budget(self):
        s = summarize_cost(DAYS, usage_file=USAGE)
        assert check_budget(s, 0.0) is True
        assert check_budget(s, 10_000.0) is False


class TestRecordAgent:
    def test_agent_field_roundtrip(self, monkeypatch, tmp_path):
        from seatunnel_agent import llm_usage
        log = tmp_path / "usage.jsonl"
        monkeypatch.delenv("LLM_USAGE_LOG", raising=False)
        monkeypatch.setenv("LLM_USAGE_PATH", str(log))
        llm_usage.record("anthropic", "claude-opus-5",
                         {"input_tokens": 10, "output_tokens": 5},
                         agent="text2sql")
        llm_usage.record("anthropic", "claude-opus-5",
                         {"input_tokens": 1, "output_tokens": 1})
        recs = [json.loads(ln) for ln in
                log.read_text(encoding="utf-8").splitlines()]
        assert recs[0]["agent"] == "text2sql"
        assert "agent" not in recs[1]  # backward compatible


class TestReport:
    def test_markdown_bilingual(self):
        s = summarize_cost(DAYS, usage_file=USAGE)
        zh = render_markdown(s, "zh")
        en = render_markdown(s, "en")
        assert "LLM 成本" in zh and "成本异常" in zh
        assert "LLM Cost" in en and "Cost anomalies" in en
        assert "my-private-llm" in zh

    def test_markdown_empty(self, tmp_path):
        s = summarize_cost(30, usage_file=tmp_path / "none.jsonl")
        assert "没有 LLM 调用记录" in render_markdown(s, "zh")


class TestCli:
    def test_markdown_report(self):
        r = CliRunner().invoke(cli, [
            "llmcost", "--days", str(DAYS),
            "--usage-path", str(USAGE)])
        assert r.exit_code == 0, r.output
        assert "LLM 成本" in r.output

    def test_json_and_output(self, tmp_path):
        out = tmp_path / "cost.json"
        r = CliRunner().invoke(cli, [
            "llmcost", "--days", str(DAYS), "-F", "json",
            "--usage-path", str(USAGE), "-o", str(out)])
        assert r.exit_code == 0, r.output
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["total"]["calls"] == 112

    def test_budget_gate_exit_1(self):
        r = CliRunner().invoke(cli, [
            "llmcost", "--days", str(DAYS), "--usage-path", str(USAGE),
            "--budget", "0.0001", "--fail-on", "budget"])
        assert r.exit_code == 1

    def test_budget_gate_pass(self):
        r = CliRunner().invoke(cli, [
            "llmcost", "--days", str(DAYS), "--usage-path", str(USAGE),
            "--budget", "99999", "--fail-on", "budget"])
        assert r.exit_code == 0

    def test_fail_on_requires_budget(self):
        r = CliRunner().invoke(cli, ["llmcost", "--fail-on", "budget"])
        assert r.exit_code != 0

    def test_malformed_pricing_exit_2(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("prices: 42", encoding="utf-8")
        r = CliRunner().invoke(cli, [
            "llmcost", "--usage-path", str(USAGE), "--pricing", str(bad)])
        assert r.exit_code == 2


class TestApi:
    def test_summary_endpoint(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.llm_cost.api import router
        monkeypatch.setenv("LLM_USAGE_PATH", str(USAGE))
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/llmcost/summary",
                          params={"days": DAYS, "budget": 0.0001,
                                  "lang": "en", "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"]["calls"] == 112
        assert data["over_budget"] is True
        assert "LLM Cost" in data["report"]

    def test_health(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.llm_cost.api import router
        app = FastAPI()
        app.include_router(router)
        resp = TestClient(app).get("/api/llmcost/health")
        assert resp.json() == {"status": "ok", "agent": "llm_cost"}
