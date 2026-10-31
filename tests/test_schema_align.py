"""Tests for the schema-align agent (65): aligner, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.schema_align import (
    align_schemas,
    parse_ddl_columns,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "schemaalign_demo"
SRC = (DEMO / "source.sql").read_text("utf-8")
SINK = (DEMO / "sink.sql").read_text("utf-8")


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_ddl_types_and_nullability():
    table, cols = parse_ddl_columns(SRC, "source")
    assert table == "orders"
    assert cols["amount"].base == "decimal"
    assert cols["amount"].args == (38, 6)
    assert cols["order_id"].not_null is True
    assert cols["user_id"].not_null is False


def test_parse_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        parse_ddl_columns("  ", "x")
    with pytest.raises(ValueError):
        parse_ddl_columns("SELECT 1;", "x")


# ── aligner ──────────────────────────────────────────────────────────

def test_demo_findings():
    result = align_schemas(SRC, SINK)
    assert result.matched == 5
    codes = {(f.code, f.column) for f in result.findings}
    assert ("SA001", "user_id") in codes
    assert ("SA002", "etl_time") in codes
    assert ("SA003", "order_id") in codes       # bigint -> int
    assert ("SA003", "amount") in codes         # decimal narrowing
    assert ("SA003", "note") in codes           # varchar truncation
    assert ("SA005", "created_at") in codes     # timestamp -> date
    assert ("SA006", "channel") in codes        # nullable -> NOT NULL


def test_missing_key_column_is_high():
    src = "CREATE TABLE t (order_id BIGINT, note STRING)"
    dst = "CREATE TABLE t2 (note STRING)"
    f = next(f for f in align_schemas(src, dst).findings
             if f.code == "SA001")
    assert f.column == "order_id" and f.severity == "high"


def test_widenings_pass_silently():
    src = ("CREATE TABLE a (id INT, d DATE, v VARCHAR(10), "
           "amt DECIMAL(10,2))")
    dst = ("CREATE TABLE b (id BIGINT, d TIMESTAMP, v STRING, "
           "amt DECIMAL(20,4))")
    result = align_schemas(src, dst)
    assert result.findings == []
    assert "safely" in render_markdown(result, lang="en")


def test_string_to_number_risky():
    src = "CREATE TABLE a (amount VARCHAR(32))"
    dst = "CREATE TABLE b (amount DECIMAL(18,2))"
    f = align_schemas(src, dst).findings[0]
    assert f.code == "SA004" and f.severity == "high"


def test_fraction_loss():
    src = "CREATE TABLE a (v DOUBLE)"
    dst = "CREATE TABLE b (v BIGINT)"
    f = align_schemas(src, dst).findings[0]
    assert f.code == "SA003" and f.detail["kind"] == "fraction_loss"


def test_extra_nullable_sink_column_ok():
    src = "CREATE TABLE a (id INT)"
    dst = "CREATE TABLE b (id INT, etl_time TIMESTAMP)"
    assert align_schemas(src, dst).findings == []
    # with a DEFAULT the NOT NULL is fine too
    dst2 = ("CREATE TABLE b (id INT, "
            "etl_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    assert align_schemas(src, dst2).findings == []


def test_report_both_langs():
    result = align_schemas(SRC, SINK)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "源目 Schema 对齐" in zh and "类型收窄" in zh
    assert "Schema Alignment" in en and "narrowing" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.schema_align import api as sa_api

    app = FastAPI()
    app.include_router(sa_api.router)
    return TestClient(app)


def test_api_align_inline():
    res = _client().post("/api/schemaalign/align",
                         json={"source_text": SRC, "sink_text": SINK,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["matched"] == 5
    assert "Schema Alignment" in body["report"]


def test_api_bad_ddl_400():
    res = _client().post("/api/schemaalign/align",
                         json={"source_text": "SELECT 1",
                               "sink_text": SINK})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("SCHEMAALIGN_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/schemaalign/align", json={
        "source_file": str(DEMO / "source.sql"),
        "sink_file": str(DEMO / "sink.sql")})
    assert res.status_code == 200
    bad = _client().post("/api/schemaalign/align", json={
        "source_file": str(ROOT / "pyproject.toml"), "sink_text": SINK})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.schema_align import advisor_llm

    monkeypatch.setattr(advisor_llm, "alignment_note",
                        lambda result, lang="zh": "ALIGN-NOTE")
    res = _client().post("/api/schemaalign/align",
                         json={"source_text": SRC, "sink_text": SINK,
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["alignment_note"] == "ALIGN-NOTE"


def test_api_health():
    body = _client().get("/api/schemaalign/health").json()
    assert body == {"status": "ok", "agent": "schema_align"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_schemaalign_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "schemaalign", "-s", str(DEMO / "source.sql"),
        "--sink", str(DEMO / "sink.sql"), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "源目 Schema 对齐" in res.output and "SA003" in res.output


def test_cli_fail_on_high_gate(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "schemaalign", "-s", str(DEMO / "source.sql"),
        "--sink", str(DEMO / "sink.sql"), "--fail-on-high"])
    assert res.exit_code == 1
    same = tmp_path / "same.sql"
    same.write_text(SRC, encoding="utf-8")
    clean = CliRunner().invoke(cli, [
        "schemaalign", "-s", str(same), "--sink", str(same),
        "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "schema_align" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.schema_align.tools import schema_align

    out = schema_align(SRC, SINK, lang="en")
    assert "Schema Alignment" in out and "SA006" in out
    assert "required" in schema_align(" ", SINK)
    assert "bad input" in schema_align("SELECT 1", SINK)
