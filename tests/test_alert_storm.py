"""Tests for the alert-storm agent (59): analyzer, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.alert_storm import (
    analyze_alerts,
    parse_alerts,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "alertstorm_demo" / "alerts.json"
EXPORT = DEMO.read_text("utf-8")


def _digest(text: str = EXPORT):
    return analyze_alerts(parse_alerts(text))


# ── analyzer ─────────────────────────────────────────────────────────

def test_demo_clusters_and_ratio():
    result = _digest()
    assert result.total == 12
    assert len(result.clusters) == 8
    assert result.dedup_ratio == 1.5
    # the kafka lag pages collapse into one cluster of 5
    top = result.clusters[0]
    assert top.count == 5 and top.sources == ["kafka"]


def test_signature_strips_numbers():
    rows = json.dumps([
        {"ts": "2026-10-31 01:00:00", "title": "lag over 100 on g"},
        {"ts": "2026-10-31 01:10:00", "title": "lag over 999 on g"}])
    result = _digest(rows)
    assert len(result.clusters) == 1


def test_storm_window_detected():
    f = next(f for f in _digest().findings if f.code == "AS002")
    assert f.severity == "high"
    assert f.detail["worst_count"] == 6
    assert f.detail["worst_start"].startswith("2026-10-31T02:10")


def test_flapping_detected():
    f = next(f for f in _digest().findings if f.code == "AS003")
    assert f.detail["firings"] == 5
    assert f.detail["window_min"] == 40.0


def test_noisy_source():
    rows = json.dumps(
        [{"ts": f"2026-10-31 0{i}:00:00", "source": "dqc",
          "title": f"check c{i} failed"} for i in range(1, 8)]
        + [{"ts": "2026-10-31 08:00:00", "source": "kafka",
            "title": "lag high"}])
    f = next(f for f in _digest(rows).findings if f.code == "AS004")
    assert f.detail["source"] == "dqc"
    assert f.detail["share_pct"] == 87.5


def test_quiet_channel_clean():
    rows = json.dumps([
        {"ts": "2026-10-31 01:00:00", "title": "a thing"},
        {"ts": "2026-10-31 05:00:00", "title": "another thing"}])
    result = _digest(rows)
    assert result.findings == []
    assert "quiet" in render_markdown(result, lang="en")


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_alerts("  ")
    with pytest.raises(ValueError):
        parse_alerts('[{"source": "x"}]')


def test_missing_ts_still_clusters():
    rows = json.dumps([{"title": "boom 1"}, {"title": "boom 2"}])
    result = _digest(rows)
    assert len(result.clusters) == 1
    assert result.clusters[0].first_ts == "-"


def test_report_both_langs():
    result = _digest()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "告警风暴摘要" in zh and "AS002" in zh
    assert "Alert Storm Digest" in en and "suppression" in en
    assert "taskfailure" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.alert_storm import api as as_api

    app = FastAPI()
    app.include_router(as_api.router)
    return TestClient(app)


def test_api_digest_inline():
    res = _client().post("/api/alertstorm/digest",
                         json={"export_text": EXPORT, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["total"] == 12
    assert "Alert Storm Digest" in body["report"]


def test_api_bad_export_400():
    res = _client().post("/api/alertstorm/digest",
                         json={"export_text": '[{"source": "x"}]'})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("ALERTSTORM_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/alertstorm/digest",
                         json={"export_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/alertstorm/digest",
                         json={"export_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.alert_storm import advisor_llm

    monkeypatch.setattr(advisor_llm, "digest_note",
                        lambda result, lang="zh": "STORM-NOTE")
    res = _client().post("/api/alertstorm/digest",
                         json={"export_text": EXPORT, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["digest_note"] == "STORM-NOTE"


def test_api_health():
    body = _client().get("/api/alertstorm/health").json()
    assert body == {"status": "ok", "agent": "alert_storm"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_alertstorm_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["alertstorm", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "告警风暴摘要" in res.output and "AS002" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["alertstorm", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    quiet = json.dumps([
        {"ts": "2026-10-31 01:00:00", "title": "a"},
        {"ts": "2026-10-31 05:00:00", "title": "b"}])
    clean = CliRunner().invoke(cli, ["alertstorm", "--text", quiet,
                                     "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "alert_storm" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.alert_storm.tools import alert_storm

    out = alert_storm(EXPORT, lang="en")
    assert "Alert Storm Digest" in out and "AS003" in out
    assert "must not be empty" in alert_storm("  ")
    assert "bad input" in alert_storm('[{"source": "x"}]')
