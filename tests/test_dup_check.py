"""Tests for the dup-check agent (37): detector, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.dup_check import detect_dups, render_markdown

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "dupcheck_demo" / "events.csv"
CSV = DEMO.read_text("utf-8")


# ── detector ─────────────────────────────────────────────────────────

def test_demo_three_layers():
    result = detect_dups(CSV, pk="event_id",
                         biz_key="user_id,action,amount")
    assert result.total_rows == 10
    assert result.row_dup_rows == 1      # e002 doubled
    assert result.pk_dup_rows == 1       # e003 twice with different source
    assert result.biz_dup_rows == 3      # u001 x3 + u003 x2
    layers = [g.layer for g in result.groups]
    assert layers == sorted(layers, key={"row": 0, "pk": 1, "biz": 2}.get)


def test_full_row_group_span_and_no_diff():
    result = detect_dups(CSV)
    g = result.groups[0]
    assert g.layer == "row" and g.count == 2
    assert (g.first_row, g.last_row) == (2, 3)
    assert g.diff_columns == []


def test_pk_group_diff_columns_locate_source():
    result = detect_dups(CSV, pk="event_id")
    g = next(g for g in result.groups if g.layer == "pk")
    assert g.key == "e003"
    assert g.diff_columns == ["source", "created_at"]


def test_identical_row_groups_not_repeated_in_key_layers():
    # e002's identical pair must appear once (row layer), not again as pk
    result = detect_dups(CSV, pk="event_id")
    pk_keys = [g.key for g in result.groups if g.layer == "pk"]
    assert "e002" not in pk_keys


def test_null_keys_skipped():
    csv = "id,v\n1,a\n,b\n,c\n"
    result = detect_dups(csv, pk="id")
    assert result.pk_dup_rows == 0 and result.groups == []


def test_unknown_key_column_raises():
    import pytest

    with pytest.raises(ValueError):
        detect_dups(CSV, pk="nope")


def test_biz_equal_to_pk_not_run_twice():
    result = detect_dups(CSV, pk="event_id", biz_key="event_id")
    assert result.biz_dup_rows == 0
    assert not [g for g in result.groups if g.layer == "biz"]


def test_clean_data():
    result = detect_dups("id,v\n1,a\n2,b\n3,c\n", pk="id")
    assert result.groups == []
    md = render_markdown(result, lang="en")
    assert "unique" in md


def test_report_both_langs():
    result = detect_dups(CSV, pk="event_id", biz_key="user_id,action,amount")
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据重复检测" in zh and "`e003`" in zh
    assert "Duplicate Check" in en and "differing columns" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.dup_check import api as dc_api

    app = FastAPI()
    app.include_router(dc_api.router)
    return TestClient(app)


def test_api_check_inline():
    res = _client().post("/api/dupcheck/check",
                         json={"data_text": CSV, "pk": "event_id",
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["pk_dup_rows"] == 1
    assert "Duplicate Check" in body["report"]


def test_api_bad_key_400():
    res = _client().post("/api/dupcheck/check",
                         json={"data_text": CSV, "pk": "missing_col"})
    assert res.status_code == 400


def test_api_empty_400():
    assert _client().post("/api/dupcheck/check",
                          json={"data_text": ""}).status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("DUPCHECK_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/dupcheck/check",
                         json={"data_file": str(DEMO), "pk": "event_id"})
    assert res.status_code == 200
    bad = _client().post("/api/dupcheck/check",
                         json={"data_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.dup_check import advisor_llm

    monkeypatch.setattr(advisor_llm, "dedup_note",
                        lambda result, lang="zh": "DEDUP-NOTE")
    res = _client().post("/api/dupcheck/check",
                         json={"data_text": CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["dedup_note"] == "DEDUP-NOTE"


def test_api_health():
    body = _client().get("/api/dupcheck/health").json()
    assert body == {"status": "ok", "agent": "dup_check"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_dupcheck_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "dupcheck", "-f", str(DEMO), "--pk", "event_id",
        "--biz-key", "user_id,action,amount", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据重复检测" in res.output and "e003" in res.output


def test_cli_fail_on_dup_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["dupcheck", "-f", str(DEMO),
                                   "--fail-on-dup"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "dupcheck", "--text", "id,v\n1,a\n2,b", "--fail-on-dup"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "dup_check" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.dup_check.tools import dup_check

    out = dup_check(CSV, pk="event_id", lang="en")
    assert "Duplicate Check" in out and "e003" in out
    assert "must not be empty" in dup_check("  ")
    assert "bad input" in dup_check(CSV, pk="nope")
