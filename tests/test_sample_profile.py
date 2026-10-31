"""Tests for the sample-profile agent (41): profiler, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.sample_profile import (
    parse_rows,
    profile_rows,
    render_markdown,
    sample_rows,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "sampleprofile_demo" / "orders.csv"

CSV = DEMO.read_text("utf-8")


def _profile(text: str, max_rows: int = 2000):
    headers, rows = parse_rows(text)
    return profile_rows(headers, sample_rows(rows, max_rows),
                        total_rows=len(rows))


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_csv_headers_and_nulls():
    headers, rows = parse_rows("a,b\n1,x\n2,NULL\n")
    assert headers == ["a", "b"]
    assert rows[1]["b"] is None


def test_parse_jsonl_union_headers_and_scalars():
    headers, rows = parse_rows(
        '{"a": 1, "b": true}\n{"a": 2.5, "c": null}\n')
    assert headers == ["a", "b", "c"]
    assert rows[0]["b"] == "true" and rows[1]["c"] is None
    assert rows[1]["a"] == "2.5"


def test_parse_json_array():
    headers, rows = parse_rows('[{"a": "x"}, {"a": "y"}]')
    assert headers == ["a"] and len(rows) == 2


def test_parse_rejects_empty_and_headerless():
    import pytest

    with pytest.raises(ValueError):
        parse_rows("   ")
    with pytest.raises(ValueError):
        parse_rows("only_header\n")


# ── sampling ─────────────────────────────────────────────────────────

def test_stride_sample_deterministic_and_capped():
    rows = [{"a": str(i)} for i in range(1000)]
    s1 = sample_rows(rows, 100)
    s2 = sample_rows(rows, 100)
    assert len(s1) == 100 and s1 == s2
    assert s1[0] == rows[0]
    assert sample_rows(rows, 5000) is rows


# ── profiling + findings ─────────────────────────────────────────────

def test_demo_profile_findings():
    result = _profile(CSV)
    assert result.total_rows == 10 and result.sampled_rows == 10
    by_name = {c.name: c for c in result.columns}
    assert by_name["order_id"].kind == "integer"
    assert by_name["email"].kind == "email"
    assert by_name["note"].kind == "empty"
    assert by_name["note"].null_pct == 100.0
    codes = {(f.code, f.column) for f in result.findings}
    assert ("SP001", "amount") in codes          # decimal + "1,299.00" text
    assert ("SP004", "created_at") in codes      # one 10/03/2026 straggler
    assert ("SP004", "email") in codes           # dave@example
    assert ("SP006", "status") in codes          # paid / PAID / 'paid '
    assert ("SP003", "note") in codes            # all-null column


def test_offender_rows_are_1_indexed():
    result = _profile(CSV)
    f = next(f for f in result.findings
             if f.code == "SP004" and f.column == "created_at")
    assert f.detail["examples"][0]["row"] == 5
    assert f.detail["examples"][0]["value"] == "10/03/2026"


def test_numeric_stats():
    result = _profile("v\n1\n2\n3\n4\n")
    col = result.columns[0]
    assert (col.vmin, col.vmax) == (1.0, 4.0)
    assert col.mean == 2.5


def test_findings_severity_order():
    result = _profile(CSV)
    sev = [f.severity for f in result.findings]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_numeric_as_text_finding():
    result = _profile('price\n"1,200"\n"3,400"\n"5,600"\n')
    codes = {f.code for f in result.findings}
    assert "SP005" in codes


def test_report_both_langs():
    result = _profile(CSV)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据抽样剖析" in zh and "SP001" in zh
    assert "Sample Profile" in en and "mixed types" in en
    assert "10" in zh


def test_report_clean_sample():
    result = _profile("a,b\n1,x\n2,y\n3,z\n")
    md = render_markdown(result, lang="en")
    assert "looks clean" in md


# ── API ──────────────────────────────────────────────────────────────

def _client(monkeypatch=None, tmp_path=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.sample_profile import api as sp_api

    app = FastAPI()
    app.include_router(sp_api.router)
    return TestClient(app)


def test_api_profile_inline():
    client = _client()
    res = client.post("/api/sampleprofile/profile",
                      json={"data_text": CSV, "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["total_rows"] == 10
    assert "Sample Profile" in body["report"]
    assert body["elapsed_ms"] >= 0


def test_api_max_rows_sampling():
    big = "v\n" + "\n".join(str(i) for i in range(500))
    client = _client()
    res = client.post("/api/sampleprofile/profile",
                      json={"data_text": big, "max_rows": 50})
    assert res.status_code == 200
    assert res.json()["result"]["sampled_rows"] == 50
    assert res.json()["result"]["total_rows"] == 500


def test_api_empty_input_400():
    client = _client()
    res = client.post("/api/sampleprofile/profile", json={"data_text": ""})
    assert res.status_code == 400


def test_api_bad_rows_400():
    client = _client()
    res = client.post("/api/sampleprofile/profile",
                      json={"data_text": "only_header"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("SAMPLEPROFILE_API_ALLOWED_DIRS", str(DEMO.parent))
    client = _client()
    res = client.post("/api/sampleprofile/profile",
                      json={"data_file": str(DEMO), "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["total_rows"] == 10
    bad = client.post("/api/sampleprofile/profile",
                      json={"data_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.sample_profile import advisor_llm

    monkeypatch.setattr(advisor_llm, "review_note",
                        lambda result, lang="zh": "NOTE-OK")
    client = _client()
    res = client.post("/api/sampleprofile/profile",
                      json={"data_text": CSV, "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["review_note"] == "NOTE-OK"
    assert "NOTE-OK" in res.json()["report"]


def test_api_health():
    body = _client().get("/api/sampleprofile/health").json()
    assert body == {"status": "ok", "agent": "sample_profile"}


# ── CLI ──────────────────────────────────────────────────────────────

def test_cli_sampleprofile_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(
        cli, ["sampleprofile", "-f", str(DEMO), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据抽样剖析" in res.output and "SP001" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(
        cli, ["sampleprofile", "-f", str(DEMO), "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(
        cli, ["sampleprofile", "--text", "a,b\n1,x\n2,y\n3,z",
              "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_cli_json_format():
    import json

    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(
        cli, ["sampleprofile", "-f", str(DEMO), "--format", "json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["total_rows"] == 10


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "sample_profile" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.sample_profile.tools import (
        sample_profile,
    )

    out = sample_profile(CSV, lang="en")
    assert "Sample Profile" in out and "SP004" in out
    assert "bad input" in sample_profile("only_header")
    assert "must not be empty" in sample_profile("  ")
