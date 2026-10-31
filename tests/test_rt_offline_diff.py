"""Tests for the rt-offline-diff agent (52): comparator, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.rt_offline_diff import (
    compare_results,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "rtoffline_demo"
RT = (DEMO / "realtime.csv").read_text("utf-8")
OFF = (DEMO / "offline.csv").read_text("utf-8")


def _compare(rt: str = RT, off: str = OFF, keys: str = "dt,channel",
             tol: float = 1.0):
    return compare_results(rt, off, keys, tolerance_pct=tol)


# ── comparator ───────────────────────────────────────────────────────

def test_demo_alignment_and_missing():
    result = _compare()
    assert result.matched == 5
    assert result.missing_in_rt == ["2026-10-29, mini"]
    assert result.missing_in_off == []


def test_mismatches_sorted_by_abs_diff():
    result = _compare()
    diffs = [abs(m["diff_pct"]) for m in result.mismatches]
    assert diffs == sorted(diffs, reverse=True)
    assert len(result.mismatches) == 6


def test_systematic_bias_rt_lower():
    result = _compare()
    by_col = {b.column: b for b in result.biases}
    assert set(by_col) == {"order_cnt", "gmv"}
    assert by_col["gmv"].direction == "rt_lower"


def test_tolerance_silences_small_diffs():
    result = _compare(tol=5.0)
    assert result.mismatches == []
    assert result.biases == []
    assert result.consistent_pct == 100.0


def test_identical_sides_clean():
    result = _compare(rt=OFF, off=OFF)
    assert result.mismatches == [] and result.missing_in_rt == []
    assert "一致" in render_markdown(result, lang="zh")


def test_rt_higher_bias():
    rt = "k,v\na,110\nb,220\nc,330\n"
    off = "k,v\na,100\nb,200\nc,300\n"
    result = _compare(rt=rt, off=off, keys="k")
    assert result.biases[0].direction == "rt_higher"


def test_null_vs_value_is_mismatch():
    rt = "k,v\na,\nb,2\n"
    off = "k,v\na,1\nb,2\n"
    result = _compare(rt=rt, off=off, keys="k")
    assert result.mismatches[0]["diff_pct"] is None


def test_bad_keys_raise():
    import pytest

    with pytest.raises(ValueError):
        _compare(keys="nope")
    with pytest.raises(ValueError):
        _compare(keys="  ")


def test_consistent_pct():
    result = _compare()
    # 3 of 5 matched keys carry a mismatch (all on 2026-10-30)
    assert result.consistent_pct == 40.0


def test_report_both_langs():
    result = _compare()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "实时与离线核对" in zh and "系统性偏差" in zh
    assert "Reconciliation" in en and "consistently LOWER" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.rt_offline_diff import api as ro_api

    app = FastAPI()
    app.include_router(ro_api.router)
    return TestClient(app)


def test_api_compare_inline():
    res = _client().post("/api/rtoffline/compare",
                         json={"realtime_text": RT, "offline_text": OFF,
                               "keys": "dt,channel", "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["matched"] == 5
    assert "Reconciliation" in body["report"]


def test_api_bad_keys_400():
    res = _client().post("/api/rtoffline/compare",
                         json={"realtime_text": RT, "offline_text": OFF,
                               "keys": "nope"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("RTOFFLINE_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/rtoffline/compare", json={
        "realtime_file": str(DEMO / "realtime.csv"),
        "offline_file": str(DEMO / "offline.csv"), "keys": "dt,channel"})
    assert res.status_code == 200
    bad = _client().post("/api/rtoffline/compare", json={
        "realtime_file": str(ROOT / "pyproject.toml"),
        "offline_text": OFF, "keys": "dt"})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.rt_offline_diff import advisor_llm

    monkeypatch.setattr(advisor_llm, "recon_note",
                        lambda result, lang="zh": "RECON-NOTE")
    res = _client().post("/api/rtoffline/compare",
                         json={"realtime_text": RT, "offline_text": OFF,
                               "keys": "dt,channel", "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["recon_note"] == "RECON-NOTE"


def test_api_health():
    body = _client().get("/api/rtoffline/health").json()
    assert body == {"status": "ok", "agent": "rt_offline_diff"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_rtoffline_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "rtoffline", "-r", str(DEMO / "realtime.csv"),
        "--offline", str(DEMO / "offline.csv"), "-k", "dt,channel",
        "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "实时与离线核对" in res.output and "系统性偏差" in res.output


def test_cli_fail_on_diff_gate(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "rtoffline", "-r", str(DEMO / "realtime.csv"),
        "--offline", str(DEMO / "offline.csv"), "-k", "dt,channel",
        "--fail-on-diff"])
    assert res.exit_code == 1
    same = tmp_path / "same.csv"
    same.write_text(OFF, encoding="utf-8")
    clean = CliRunner().invoke(cli, [
        "rtoffline", "-r", str(same), "--offline", str(same),
        "-k", "dt,channel", "--fail-on-diff"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "rt_offline_diff" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.rt_offline_diff.tools import (
        rt_offline_diff,
    )

    out = rt_offline_diff(RT, OFF, "dt,channel", lang="en")
    assert "Reconciliation" in out and "rt_lower" not in out
    assert "required" in rt_offline_diff(" ", OFF, "dt")
    assert "bad input" in rt_offline_diff(RT, OFF, "nope")


# ── late-data grace window ───────────────────────────────────────────

def test_grace_excludes_newest_key_values():
    result = compare_results(RT, OFF, "dt,channel", tolerance_pct=1.0,
                             grace_key="dt", grace=1)
    # every demo mismatch sits on 2026-10-30 -> excluded -> consistent
    assert result.grace_excluded == ["2026-10-30"]
    assert result.mismatches == [] and result.biases == []
    assert result.consistent_pct == 100.0
    # the 10-29 missing key survives the grace
    assert result.missing_in_rt == ["2026-10-29, mini"]


def test_grace_zero_is_noop():
    a = compare_results(RT, OFF, "dt,channel").to_dict()
    b = compare_results(RT, OFF, "dt,channel", grace_key="dt",
                        grace=0).to_dict()
    b["grace_key"] = a["grace_key"]       # only the echo differs
    assert a == b


def test_grace_key_must_be_a_key_column():
    import pytest

    with pytest.raises(ValueError):
        compare_results(RT, OFF, "dt,channel", grace_key="gmv", grace=1)


def test_cli_grace_options(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "rtoffline", "-r", str(DEMO / "realtime.csv"),
        "--offline", str(DEMO / "offline.csv"), "-k", "dt,channel",
        "--grace-key", "dt", "--grace", "1", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "宽限" in res.output and "100.0%" in res.output
