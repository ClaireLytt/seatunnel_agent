"""Tests for the metric-attribution agent (60): attributor, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.metric_attribution import (
    attribute_change,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "metricattribution_demo"
BASE = (DEMO / "baseline.csv").read_text("utf-8")
CUR = (DEMO / "current.csv").read_text("utf-8")


def _attr(dims: str = "channel,region", metric: str = "gmv",
          base: str = BASE, cur: str = CUR):
    return attribute_change(base, cur, dims, metric)


# ── attributor ───────────────────────────────────────────────────────

def test_demo_totals_and_delta():
    result = _attr()
    assert result.total_base == 150000.0
    assert result.total_cur == 137000.0
    assert result.delta == -13000.0
    assert result.delta_pct == -8.67


def test_decomposition_is_additive():
    result = _attr()
    for b in result.breakdowns:
        assert round(sum(m["contribution"] for m in b.movers), 2) == \
            round(result.delta, 2)


def test_top_contributor_identified():
    result = _attr()
    ma001 = [f for f in result.findings if f.code == "MA001"]
    by_dim = {f.detail["dimension"]: f.detail for f in ma001}
    assert by_dim["channel"]["value"] == "app"
    assert by_dim["channel"]["contribution"] == -15500.0
    assert by_dim["region"]["value"] == "north"


def test_concentration_verdict():
    codes = [(f.code, f.detail.get("dimension"))
             for f in _attr().findings]
    assert ("MA002", "channel") in codes


def test_mix_shift_detected():
    base = "d,v\na,100\nb,100\n"
    cur = "d,v\na,180\nb,25\n"          # +80 and -75 net +5
    result = _attr(dims="d", metric="v", base=base, cur=cur)
    assert any(f.code == "MA003" for f in result.findings)


def test_appeared_and_vanished_values():
    base = "d,v\na,100\nb,50\n"
    cur = "d,v\na,100\nc,70\n"
    result = _attr(dims="d", metric="v", base=base, cur=cur)
    movers = {m["value"]: m for m in result.breakdowns[0].movers}
    assert movers["b"]["status"] == "vanished"
    assert movers["b"]["contribution"] == -50.0
    assert movers["c"]["status"] == "appeared"


def test_flat_totals():
    result = _attr(base=BASE, cur=BASE)
    assert result.delta == 0.0
    assert "无需归因" in render_markdown(result, lang="zh")


def test_bad_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        _attr(dims="")
    with pytest.raises(ValueError):
        _attr(metric="nope")
    with pytest.raises(ValueError):
        _attr(dims="ghost")


def test_report_both_langs():
    result = _attr()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "指标异动归因" in zh and "`app`" in zh
    assert "Metric Change Attribution" in en and "qualitytrace" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.metric_attribution import api as ma_api

    app = FastAPI()
    app.include_router(ma_api.router)
    return TestClient(app)


def test_api_attribute_inline():
    res = _client().post("/api/metricattribution/attribute",
                         json={"baseline_text": BASE, "current_text": CUR,
                               "dims": "channel", "metric": "gmv",
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["delta"] == -13000.0
    assert "Metric Change Attribution" in body["report"]


def test_api_bad_column_400():
    res = _client().post("/api/metricattribution/attribute",
                         json={"baseline_text": BASE, "current_text": CUR,
                               "dims": "ghost", "metric": "gmv"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("METRICATTRIBUTION_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/metricattribution/attribute", json={
        "baseline_file": str(DEMO / "baseline.csv"),
        "current_file": str(DEMO / "current.csv"),
        "dims": "channel", "metric": "gmv"})
    assert res.status_code == 200
    bad = _client().post("/api/metricattribution/attribute", json={
        "baseline_file": str(ROOT / "pyproject.toml"),
        "current_text": CUR, "dims": "channel", "metric": "gmv"})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.metric_attribution import advisor_llm

    monkeypatch.setattr(advisor_llm, "attribution_note",
                        lambda result, lang="zh": "ATTR-NOTE")
    res = _client().post("/api/metricattribution/attribute",
                         json={"baseline_text": BASE, "current_text": CUR,
                               "dims": "channel", "metric": "gmv",
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["attribution_note"] == "ATTR-NOTE"


def test_api_health():
    body = _client().get("/api/metricattribution/health").json()
    assert body == {"status": "ok", "agent": "metric_attribution"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_metricattr_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "metricattr", "-b", str(DEMO / "baseline.csv"),
        "-c", str(DEMO / "current.csv"), "--dims", "channel,region",
        "--metric", "gmv", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "指标异动归因" in res.output and "app" in res.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "metric_attribution" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.metric_attribution.tools import (
        metric_attribution,
    )

    out = metric_attribution(BASE, CUR, "channel", "gmv", lang="en")
    assert "Metric Change Attribution" in out and "MA001" in out
    assert "required" in metric_attribution(" ", CUR, "channel", "gmv")
    assert "bad input" in metric_attribution(BASE, CUR, "ghost", "gmv")
