"""Tests for the capacity-forecast agent (57): forecaster, report, API, CLI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from seatunnel_agent.agents.data.capacity_forecast import (
    forecast_capacity,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "capacityforecast_demo" / "storage.csv"
CSV = DEMO.read_text("utf-8")
TODAY = date(2026, 10, 31)


def _forecast(quota: float = 2000, text: str = CSV, window: int = 14):
    return forecast_capacity(text, quota=quota, window=window, today=TODAY)


# ── forecaster ───────────────────────────────────────────────────────

def test_demo_exhaustion_math():
    result = _forecast()
    assert result.total_latest == 1060.0
    assert round(result.total_daily_growth) == 20
    assert result.days_left == 47.0
    assert result.exhaustion_date == "2026-12-17"


def test_horizon_grading():
    mid = _forecast(quota=2000)      # 47 days -> mid
    assert mid.findings[0].code == "CF001"
    assert mid.findings[0].severity == "mid"
    high = _forecast(quota=1200)     # 7 days -> high
    assert high.findings[0].severity == "high"
    far = _forecast(quota=10000)     # ~447 days -> no CF001
    assert not any(f.code == "CF001" for f in far.findings)


def test_already_over_quota():
    result = _forecast(quota=1000)
    assert result.days_left == 0.0
    assert result.exhaustion_date == TODAY.isoformat()


def test_top_growers_and_shrinkers():
    result = _forecast()
    growers = next(f for f in result.findings if f.code == "CF002")
    assert growers.detail["top"][0]["metric"] == "ods.click_log"
    shrink = next(f for f in result.findings if f.code == "CF003")
    assert shrink.detail["metrics"][0]["metric"] == "bak.orders_v1"


def test_named_total_metric_wins():
    rows = "date,metric,value\n" + "\n".join(
        f"2026-10-{d:02d},total,{1000 + d * 10}" for d in range(17, 31))
    result = _forecast(quota=2000, text=rows)
    assert result.total_latest == 1300.0
    assert round(result.total_daily_growth) == 10


def test_flat_series_never_exhausts():
    rows = "date,metric,value\n" + "\n".join(
        f"2026-10-{d:02d},t,500" for d in range(17, 31))
    result = _forecast(quota=1000, text=rows)
    assert result.days_left is None
    assert result.exhaustion_date == "-"
    md = render_markdown(result, lang="en")
    assert "fits the quota" in md


def test_bad_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        _forecast(quota=0)
    with pytest.raises(ValueError):
        forecast_capacity("  ", quota=100)


def test_report_both_langs():
    result = _forecast()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "容量耗尽预测" in zh and "2026-12-17" in zh
    assert "Capacity Forecast" in en and "LINEAR" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.capacity_forecast import api as cf_api

    app = FastAPI()
    app.include_router(cf_api.router)
    return TestClient(app)


def test_api_forecast_inline():
    res = _client().post("/api/capacityforecast/forecast",
                         json={"series_text": CSV, "quota": 2000,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["total_latest"] == 1060.0
    assert "Capacity Forecast" in body["report"]


def test_api_bad_inputs_400():
    assert _client().post("/api/capacityforecast/forecast",
                          json={"series_text": "x,y\n1,2",
                                "quota": 100}).status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("CAPACITYFORECAST_API_ALLOWED_DIRS",
                       str(DEMO.parent))
    res = _client().post("/api/capacityforecast/forecast",
                         json={"series_file": str(DEMO), "quota": 2000})
    assert res.status_code == 200
    bad = _client().post("/api/capacityforecast/forecast",
                         json={"series_file": str(ROOT / "pyproject.toml"),
                               "quota": 2000})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.capacity_forecast import advisor_llm

    monkeypatch.setattr(advisor_llm, "capacity_note",
                        lambda result, lang="zh": "CAP-NOTE")
    res = _client().post("/api/capacityforecast/forecast",
                         json={"series_text": CSV, "quota": 2000,
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["capacity_note"] == "CAP-NOTE"


def test_api_health():
    body = _client().get("/api/capacityforecast/health").json()
    assert body == {"status": "ok", "agent": "capacity_forecast"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_capacityforecast_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "capacityforecast", "-f", str(DEMO), "--quota", "2000",
        "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "容量耗尽预测" in res.output and "ods.click_log" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "capacityforecast", "-f", str(DEMO), "--quota", "1200",
        "--fail-on-high"])
    assert res.exit_code == 1
    ok = CliRunner().invoke(cli, [
        "capacityforecast", "-f", str(DEMO), "--quota", "10000",
        "--fail-on-high"])
    assert ok.exit_code == 0, ok.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "capacity_forecast" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.capacity_forecast.tools import (
        capacity_forecast,
    )

    out = capacity_forecast(CSV, quota=2000, lang="en")
    assert "Capacity Forecast" in out and "CF002" in out
    assert "must not be empty" in capacity_forecast("  ", quota=100)
    assert "bad input" in capacity_forecast(CSV, quota=0)
