"""Tests for the rt-latency agent (50): analyzer, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.rt_latency import (
    analyze_latency,
    parse_events,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "rtlatency_demo" / "events.csv"
CSV = DEMO.read_text("utf-8")


def _analyze(text: str = CSV, sla_ms: float = 0.0):
    stages, events = parse_events(text)
    return analyze_latency(stages, events, sla_ms=sla_ms)


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_csv_stages():
    stages, events = parse_events(CSV)
    assert stages == ["produce_ts", "ingest_ts", "process_ts", "sink_ts"]
    assert len(events) == 8
    assert events[0]["event_id"] == "e001"


def test_parse_jsonl_epoch_ms():
    jl = ('{"event_id": "a", "produce_ts": 1700000000000, '
          '"sink_ts": 1700000000500}\n')
    stages, events = parse_events(jl)
    assert stages == ["produce_ts", "sink_ts"]
    assert events[0]["sink_ts"] - events[0]["produce_ts"] == 500.0


def test_parse_epoch_seconds_scaled():
    jl = ('{"event_id": "a", "produce_ts": 1700000000, '
          '"sink_ts": 1700000001}\n')
    _, events = parse_events(jl)
    assert events[0]["sink_ts"] - events[0]["produce_ts"] == 1000.0


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_events("  ")
    with pytest.raises(ValueError):
        parse_events("event_id,produce_ts\ne1,2026-01-01\n")   # one stage
    with pytest.raises(ValueError):
        parse_events("event_id,a_ts,b_ts\ne1,notatime,2026-01-01\n")


# ── analyzer ─────────────────────────────────────────────────────────

def test_dominant_hop_and_stats():
    result = _analyze()
    assert result.dominant_hop == "ingest→process"
    hops = {s.hop: s for s in result.stages}
    assert hops["produce→ingest"].p50_ms == 210.0
    assert result.e2e is not None and result.e2e.max_ms == 73400.0


def test_outlier_event_with_worst_hop():
    result = _analyze()
    assert len(result.outliers) == 1
    o = result.outliers[0]
    assert o["event_id"] == "e008"
    assert o["worst_hop"] == "ingest→process"


def test_sla_breaches():
    result = _analyze(sla_ms=2000)
    assert result.breaches == 1
    assert _analyze(sla_ms=100000).breaches == 0


def test_missing_stage_skipped_per_event():
    csv = ("event_id,a_ts,b_ts,c_ts\n"
           "e1,1700000000000,1700000000100,1700000000300\n"
           "e2,1700000000000,,1700000000400\n")
    result = _analyze(csv)
    hops = {s.hop: s for s in result.stages}
    assert hops["a→b"].count == 1
    assert hops["a→c"].count == 1          # e2 bridges the missing stage
    assert result.e2e.count == 2


def test_negative_gap_clamped():
    csv = ("event_id,a_ts,b_ts\n"
           "e1,1700000000500,1700000000400\n"
           "e2,1700000000000,1700000000100\n")
    result = _analyze(csv)
    assert result.stages[0].max_ms == 100.0


def test_report_both_langs():
    result = _analyze(sla_ms=2000)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "端到端延迟分析" in zh and "e008" in zh
    assert "End-to-End Latency" in en and "ingest→process" in en
    assert "2000" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.rt_latency import api as rl_api

    app = FastAPI()
    app.include_router(rl_api.router)
    return TestClient(app)


def test_api_analyze_inline():
    res = _client().post("/api/rtlatency/analyze",
                         json={"events_text": CSV, "sla_ms": 2000,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["dominant_hop"] == "ingest→process"
    assert body["result"]["breaches"] == 1
    assert "End-to-End Latency" in body["report"]


def test_api_bad_rows_400():
    res = _client().post("/api/rtlatency/analyze",
                         json={"events_text": "event_id\ne1\n"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("RTLATENCY_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/rtlatency/analyze",
                         json={"events_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/rtlatency/analyze",
                         json={"events_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.rt_latency import advisor_llm

    monkeypatch.setattr(advisor_llm, "latency_note",
                        lambda result, lang="zh": "LAT-NOTE")
    res = _client().post("/api/rtlatency/analyze",
                         json={"events_text": CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["latency_note"] == "LAT-NOTE"


def test_api_health():
    body = _client().get("/api/rtlatency/health").json()
    assert body == {"status": "ok", "agent": "rt_latency"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_rtlatency_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["rtlatency", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "端到端延迟分析" in res.output and "e008" in res.output


def test_cli_fail_on_breach_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["rtlatency", "-f", str(DEMO),
                                   "--sla-ms", "2000",
                                   "--fail-on-breach"])
    assert res.exit_code == 1
    ok = CliRunner().invoke(cli, ["rtlatency", "-f", str(DEMO),
                                  "--sla-ms", "200000",
                                  "--fail-on-breach"])
    assert ok.exit_code == 0, ok.output
    missing = CliRunner().invoke(cli, ["rtlatency", "-f", str(DEMO),
                                       "--fail-on-breach"])
    assert missing.exit_code == 2


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "rt_latency" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.rt_latency.tools import rt_latency

    out = rt_latency(CSV, lang="en")
    assert "End-to-End Latency" in out and "e008" in out
    assert "must not be empty" in rt_latency("  ")
    assert "bad input" in rt_latency("event_id\ne1\n")
