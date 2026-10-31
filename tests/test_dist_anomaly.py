"""Tests for the dist-anomaly agent (36): comparator, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.dist_anomaly import (
    compare_profiles,
    load_profile,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "distanomaly_demo"
BASE = (DEMO / "baseline.csv").read_text("utf-8")
CUR = (DEMO / "current.csv").read_text("utf-8")


def _compare(base: str = BASE, cur: str = CUR):
    return compare_profiles(load_profile(base), load_profile(cur))


# ── load_profile ─────────────────────────────────────────────────────

def test_load_profile_from_rows_and_from_json():
    p1 = load_profile(BASE)
    assert p1["total_rows"] == 10
    # a ready profile JSON round-trips untouched
    p2 = load_profile(json.dumps(p1))
    assert p2 == p1


def test_load_profile_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        load_profile("   ")


# ── comparator ───────────────────────────────────────────────────────

def test_demo_drift_findings():
    result = _compare()
    assert result.columns_compared == 3
    codes = {(f.code, f.column, f.severity) for f in result.findings}
    assert ("DA001", "coupon", "high") in codes       # removed column
    assert ("DA001", "discount", "mid") in codes      # added column
    assert ("DA002", "amount", "high") in codes       # mean doubled
    assert ("DA003", "amount", "high") in codes       # nulls 0 -> 30pp
    assert ("DA004", "channel", "high") in codes      # app/web -> mini
    assert ("DA005", "channel", "low") in codes       # new + vanished cat


def test_identical_samples_have_no_findings():
    result = _compare(BASE, BASE)
    assert result.findings == []


def test_mean_shift_grading():
    base = "v\n100\n100\n100\n"
    mid = "v\n125\n125\n125\n"      # 25% shift -> mid
    high = "v\n160\n160\n160\n"     # 60% shift -> high
    assert {f.severity for f in _compare(base, mid).findings
            if f.code == "DA002"} == {"mid"}
    assert {f.severity for f in _compare(base, high).findings
            if f.code == "DA002"} == {"high"}


def test_kind_change_detected():
    result = _compare("v\n1\n2\n3\n", "v\nx\ny\nz\n")
    assert any(f.code == "DA007" and f.severity == "high"
               for f in result.findings)


def test_category_drift_skips_id_like_columns():
    base = "id\na1\na2\na3\na4\n"
    cur = "id\nb1\nb2\nb3\nb4\n"
    codes = {f.code for f in _compare(base, cur).findings}
    assert "DA004" not in codes and "DA005" not in codes


def test_findings_sorted_by_severity():
    sev = [f.severity for f in _compare().findings]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_report_both_langs():
    result = _compare()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据分布漂移" in zh and "DA002" in zh
    assert "Distribution Drift" in en and "mean shift" in en


def test_report_clean():
    md = render_markdown(_compare(BASE, BASE), lang="en")
    assert "look alike" in md


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.dist_anomaly import api as da_api

    app = FastAPI()
    app.include_router(da_api.router)
    return TestClient(app)


def test_api_compare_inline():
    res = _client().post("/api/distanomaly/compare",
                         json={"baseline_text": BASE, "current_text": CUR,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["columns_compared"] == 3
    assert "Distribution Drift" in body["report"]


def test_api_missing_side_400():
    res = _client().post("/api/distanomaly/compare",
                         json={"baseline_text": BASE})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("DISTANOMALY_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/distanomaly/compare", json={
        "baseline_file": str(DEMO / "baseline.csv"),
        "current_file": str(DEMO / "current.csv")})
    assert res.status_code == 200
    bad = _client().post("/api/distanomaly/compare", json={
        "baseline_file": str(ROOT / "pyproject.toml"),
        "current_text": CUR})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.dist_anomaly import advisor_llm

    monkeypatch.setattr(advisor_llm, "drift_note",
                        lambda result, lang="zh": "DRIFT-NOTE")
    res = _client().post("/api/distanomaly/compare",
                         json={"baseline_text": BASE, "current_text": CUR,
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["drift_note"] == "DRIFT-NOTE"
    assert "DRIFT-NOTE" in res.json()["report"]


def test_api_health():
    body = _client().get("/api/distanomaly/health").json()
    assert body == {"status": "ok", "agent": "dist_anomaly"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_distanomaly_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "distanomaly", "-b", str(DEMO / "baseline.csv"),
        "-c", str(DEMO / "current.csv"), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据分布漂移" in res.output and "DA002" in res.output


def test_cli_fail_on_high_gate(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "distanomaly", "-b", str(DEMO / "baseline.csv"),
        "-c", str(DEMO / "current.csv"), "--fail-on-high"])
    assert res.exit_code == 1
    same = tmp_path / "same.csv"
    same.write_text(BASE, encoding="utf-8")
    clean = CliRunner().invoke(cli, [
        "distanomaly", "-b", str(same), "-c", str(same), "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "dist_anomaly" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.dist_anomaly.tools import dist_anomaly

    out = dist_anomaly(BASE, CUR, lang="en")
    assert "Distribution Drift" in out and "DA004" in out
    assert "required" in dist_anomaly(BASE, " ")
    assert "bad input" in dist_anomaly("only_header", "only_header")
