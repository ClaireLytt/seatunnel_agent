"""Tests for the kafka-lag agent (48): analyzer, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.kafka_lag import (
    analyze_lag,
    parse_lag_snapshot,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "kafkalag_demo" / "snapshot.json"
SNAP = DEMO.read_text("utf-8")


def _diag(text: str = SNAP):
    group, parts = parse_lag_snapshot(text)
    return analyze_lag(group, parts)


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_json_snapshot():
    group, parts = parse_lag_snapshot(SNAP)
    assert group == "g-orders" and len(parts) == 5
    assert parts[2].lag == 900000


def test_parse_csv_snapshot():
    csv = ("topic,partition,log_end_offset,committed_offset,"
           "consume_rate,produce_rate\n"
           "orders,0,1000,900,10,8\n"
           "orders,1,1000,500,,\n")
    group, parts = parse_lag_snapshot(csv)
    assert group == "" and len(parts) == 2
    assert parts[1].consume_rate is None


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_lag_snapshot("  ")
    with pytest.raises(ValueError):
        parse_lag_snapshot('{"group": "g", "topics": []}')
    with pytest.raises(ValueError):
        parse_lag_snapshot("partition,log_end_offset\n0,100\n")


# ── analyzer ─────────────────────────────────────────────────────────

def test_demo_findings():
    result = _diag()
    codes = {f.code for f in result.findings}
    assert codes == {"KL001", "KL002", "KL003", "KL004", "KL005"}
    assert result.total_lag == 1089000


def test_hot_partition_evidence():
    f = next(f for f in _diag().findings if f.code == "KL002")
    assert f.detail["topic"] == "orders" and f.detail["partition"] == 2
    assert f.detail["ratio"] == 10.0


def test_stalled_partition():
    f = next(f for f in _diag().findings if f.code == "KL004")
    assert f.detail["partition"] == 3 and f.severity == "high"


def test_catch_up_eta():
    f = next(f for f in _diag().findings if f.code == "KL005")
    assert f.detail["topic"] == "payments"
    assert f.detail["eta_min"] == 37.5


def test_healthy_group_clean():
    snap = json.dumps({"group": "g", "topics": [{
        "topic": "t", "partitions": [
            {"partition": 0, "log_end_offset": 1000,
             "committed_offset": 990, "consume_rate": 100,
             "produce_rate": 80},
            {"partition": 1, "log_end_offset": 1000,
             "committed_offset": 995, "consume_rate": 100,
             "produce_rate": 80}]}]})
    result = _diag(snap)
    assert result.findings == []
    assert "keeping up" in render_markdown(result, lang="en")


def test_rate_rules_quiet_without_rates():
    snap = json.dumps({"group": "g", "topics": [{
        "topic": "t", "partitions": [
            {"partition": 0, "log_end_offset": 2_000_000,
             "committed_offset": 0}]}]})
    codes = {f.code for f in _diag(snap).findings}
    assert "KL001" in codes
    assert not codes & {"KL003", "KL004", "KL005"}


def test_partitions_sorted_by_lag():
    result = _diag()
    lags = [p.lag for p in result.partitions]
    assert lags == sorted(lags, reverse=True)


def test_report_both_langs():
    result = _diag()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "Kafka 消费积压诊断" in zh and "KL004" in zh
    assert "Kafka Consumer-Lag Diagnosis" in en and "catch-up" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.kafka_lag import api as kl_api

    app = FastAPI()
    app.include_router(kl_api.router)
    return TestClient(app)


def test_api_diagnose_inline():
    res = _client().post("/api/kafkalag/diagnose",
                         json={"snapshot_text": SNAP, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["total_lag"] == 1089000
    assert "Kafka Consumer-Lag Diagnosis" in body["report"]


def test_api_bad_snapshot_400():
    res = _client().post("/api/kafkalag/diagnose",
                         json={"snapshot_text": '{"topics": []}'})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("KAFKALAG_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/kafkalag/diagnose",
                         json={"snapshot_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/kafkalag/diagnose",
                         json={"snapshot_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.kafka_lag import advisor_llm

    monkeypatch.setattr(advisor_llm, "ops_note",
                        lambda result, lang="zh": "LAG-NOTE")
    res = _client().post("/api/kafkalag/diagnose",
                         json={"snapshot_text": SNAP, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["ops_note"] == "LAG-NOTE"


def test_api_health():
    body = _client().get("/api/kafkalag/health").json()
    assert body == {"status": "ok", "agent": "kafka_lag"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_kafkalag_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["kafkalag", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "Kafka 消费积压诊断" in res.output and "KL002" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["kafkalag", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    healthy = json.dumps({"group": "g", "topics": [{
        "topic": "t", "partitions": [
            {"partition": 0, "log_end_offset": 100,
             "committed_offset": 100}]}]})
    clean = CliRunner().invoke(cli, ["kafkalag", "--text", healthy,
                                     "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "kafka_lag" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.kafka_lag.tools import kafka_lag

    out = kafka_lag(SNAP, lang="en")
    assert "Kafka Consumer-Lag Diagnosis" in out and "KL003" in out
    assert "must not be empty" in kafka_lag("  ")
    assert "bad input" in kafka_lag('{"topics": []}')
