"""Tests for the data-volatility agent (39): analyzer, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.data_volatility import (
    analyze_series,
    parse_series,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "datavolatility_demo" / "daily_orders.csv"
CSV = DEMO.read_text("utf-8")


def _analyze(text: str = CSV):
    return analyze_series(parse_series(text))


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_groups_and_sorts():
    series = parse_series("date,metric,value\n"
                          "2026-10-02,a,2\n2026-10-01,a,1\n2026-10-01,b,9\n")
    assert set(series) == {"a", "b"}
    assert series["a"] == [("2026-10-01", 1.0), ("2026-10-02", 2.0)]


def test_parse_jsonl_and_default_metric():
    series = parse_series('{"date": "2026-10-01", "value": 5}\n'
                          '{"date": "2026-10-02", "value": 6}\n')
    assert list(series) == ["value"] and len(series["value"]) == 2


def test_parse_rejects_bad_rows():
    import pytest

    with pytest.raises(ValueError):
        parse_series("   ")
    with pytest.raises(ValueError):
        parse_series("date,metric,value\n2026-10-01,a,notnum\n")
    with pytest.raises(ValueError):
        parse_series("date,metric,value\n2026-10-01,a,\n")


# ── analyzer ─────────────────────────────────────────────────────────

def test_demo_findings():
    result = _analyze()
    assert result.metrics == {"active_users": 8, "gmv": 7, "order_cnt": 9}
    codes = {(f.code, f.metric) for f in result.findings}
    assert ("VA001", "order_cnt") in codes       # 2300 surge on 10-07
    assert ("VA003", "gmv") in codes             # 98k -> 52k level shift
    assert ("VA004", "active_users") in codes    # frozen at 4800
    assert ("VA005", "order_cnt") in codes       # 10-09 missing


def test_surge_evidence():
    f = next(f for f in _analyze().findings
             if f.code == "VA001" and f.metric == "order_cnt")
    assert f.severity == "high"
    assert f.detail["date"] == "2026-10-07"
    assert f.detail["value"] == 2300.0


def test_drop_detected():
    rows = ["date,metric,value"] + [
        f"2026-10-{d:02d},m,100" for d in range(1, 8)] + [
        "2026-10-08,m,20"]
    result = _analyze("\n".join(rows))
    assert any(f.code == "VA002" and f.severity == "high"
               for f in result.findings)


def test_steady_series_clean():
    rows = ["date,metric,value"] + [
        f"2026-10-{d:02d},m,{100 + (d % 3)}" for d in range(1, 11)]
    result = _analyze("\n".join(rows))
    assert result.findings == []


def test_single_spike_not_double_reported_as_shift():
    # spike at the very end: VA001 fires, VA003 must not pile on
    rows = ["date,metric,value"] + [
        f"2026-10-{d:02d},m,100" for d in range(1, 10)] + [
        "2026-10-10,m,300"]
    codes = [f.code for f in _analyze("\n".join(rows)).findings]
    assert "VA001" in codes and "VA003" not in codes


def test_non_iso_dates_skip_gap_check():
    rows = ["date,metric,value",
            "d1,m,1", "d2,m,2", "d9,m,3"]
    codes = {f.code for f in _analyze("\n".join(rows)).findings}
    assert "VA005" not in codes


def test_report_both_langs():
    result = _analyze()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据波动分析" in zh and "VA001" in zh
    assert "Data Volatility" in en and "level shift" in en
    assert "qualitytrace" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_volatility import api as dv_api

    app = FastAPI()
    app.include_router(dv_api.router)
    return TestClient(app)


def test_api_analyze_inline():
    res = _client().post("/api/datavolatility/analyze",
                         json={"series_text": CSV, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["metrics"]["order_cnt"] == 9
    assert "Data Volatility" in body["report"]


def test_api_bad_input_400():
    res = _client().post("/api/datavolatility/analyze",
                         json={"series_text": "date,metric,value\nx,a,NaNo"})
    assert res.status_code == 400
    assert _client().post("/api/datavolatility/analyze",
                          json={"series_text": ""}).status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("DATAVOLATILITY_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/datavolatility/analyze",
                         json={"series_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/datavolatility/analyze",
                         json={"series_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.data_volatility import advisor_llm

    monkeypatch.setattr(advisor_llm, "volatility_note",
                        lambda result, lang="zh": "VOL-NOTE")
    res = _client().post("/api/datavolatility/analyze",
                         json={"series_text": CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["volatility_note"] == "VOL-NOTE"


def test_api_health():
    body = _client().get("/api/datavolatility/health").json()
    assert body == {"status": "ok", "agent": "data_volatility"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_datavolatility_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "datavolatility", "-f", str(DEMO), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据波动分析" in res.output and "VA001" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["datavolatility", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    steady = "date,metric,value\n" + "\n".join(
        f"2026-10-{d:02d},m,100" for d in range(1, 8))
    clean = CliRunner().invoke(cli, ["datavolatility", "--text", steady,
                                     "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "data_volatility" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.data_volatility.tools import (
        data_volatility,
    )

    out = data_volatility(CSV, lang="en")
    assert "Data Volatility" in out and "VA003" in out
    assert "must not be empty" in data_volatility("  ")
    assert "bad input" in data_volatility("date,metric,value\nx,a,zzz")


def test_dod_and_pop_changes_on_latest_point():
    # steady series, then the latest point jumps 40% - not enough for a
    # spike (needs 50%) but a VA006 DoD change; with period=3 the same
    # point also fires VA007 vs three points earlier
    rows = ["date,metric,value"] + [
        f"2026-10-{d:02d},m,100" for d in range(1, 8)] + [
        "2026-10-08,m,140"]
    series = parse_series("\n".join(rows))
    result = analyze_series(series, period=3)
    codes = {f.code for f in result.findings}
    assert "VA006" in codes and "VA007" in codes
    dod = next(f for f in result.findings if f.code == "VA006")
    assert dod.detail["change_pct"] == 40.0


def test_spiked_point_not_double_reported_as_dod():
    rows = ["date,metric,value"] + [
        f"2026-10-{d:02d},m,100" for d in range(1, 8)] + [
        "2026-10-08,m,300"]
    codes = {f.code for f in
             analyze_series(parse_series("\n".join(rows))).findings}
    assert "VA001" in codes and "VA006" not in codes


def test_cli_period_option():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    rows = "date,metric,value\n" + "\n".join(
        f"2026-10-{d:02d},m,100" for d in range(1, 8)) + "\n2026-10-08,m,140"
    res = CliRunner().invoke(cli, ["datavolatility", "--text", rows,
                                   "--period", "3", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "VA006" in res.output and "VA007" in res.output
