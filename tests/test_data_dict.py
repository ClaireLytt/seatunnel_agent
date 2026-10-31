"""Tests for the data-dict agent (43): generator, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.data_dict import (
    generate_dict,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "examples" / "datadict_demo" / "catalog.json").read_text(
    "utf-8")
WORKLOAD = (ROOT / "examples" / "datadict_demo" / "workload.sql").read_text(
    "utf-8")

DDL_NO_COMMENTS = """
CREATE TABLE t (
  id BIGINT,
  created_at TIMESTAMP,
  is_active TINYINT,
  amount DECIMAL(18,2),
  city STRING COMMENT 'city'
);
"""


# ── generator ────────────────────────────────────────────────────────

def test_roles_inferred_from_name_shapes():
    result = generate_dict(DDL_NO_COMMENTS)
    roles = {e.name: e.role for e in result.tables[0].entries}
    assert roles == {"id": "key", "created_at": "time",
                     "is_active": "flag", "amount": "measure",
                     "city": "dimension"}


def test_comment_coverage():
    result = generate_dict(DDL_NO_COMMENTS)
    assert result.tables[0].comment_coverage == 20.0


def test_usage_mined_from_workload():
    result = generate_dict(CATALOG, sql_text=WORKLOAD)
    daily = next(t for t in result.tables if t.table == "dws.orders_daily")
    by_name = {e.name: e for e in daily.entries}
    assert by_name["order_date"].filter_uses == 1
    assert by_name["user_id"].join_uses == 2
    assert by_name["user_id"].group_uses == 1


def test_no_workload_zero_usage():
    result = generate_dict(CATALOG)
    for t in result.tables:
        for e in t.entries:
            assert (e.filter_uses, e.join_uses, e.group_uses) == (0, 0, 0)


def test_bad_catalog_raises():
    import pytest

    with pytest.raises(ValueError):
        generate_dict("SELECT 1;")


def test_report_both_langs():
    result = generate_dict(CATALOG, sql_text=WORKLOAD)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据字典" in zh and "`gmv`" in zh
    assert "Data Dictionary" in en and "comment coverage" in en


def test_report_marks_missing_comments():
    md = render_markdown(generate_dict(DDL_NO_COMMENTS), lang="en")
    assert "—" in md and "20%" in md


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_dict import api as dd_api

    app = FastAPI()
    app.include_router(dd_api.router)
    return TestClient(app)


def test_api_generate_inline():
    res = _client().post("/api/datadict/generate",
                         json={"catalog_text": CATALOG,
                               "sql_text": WORKLOAD,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["tables"]) == 5
    assert "Data Dictionary" in body["report"]


def test_api_bad_catalog_400():
    res = _client().post("/api/datadict/generate",
                         json={"catalog_text": "SELECT 1;"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    demo = ROOT / "examples" / "datadict_demo"
    monkeypatch.setenv("DATADICT_API_ALLOWED_DIRS", str(demo))
    res = _client().post("/api/datadict/generate",
                         json={"catalog_file": str(demo / "catalog.json")})
    assert res.status_code == 200
    bad = _client().post("/api/datadict/generate",
                         json={"catalog_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.data_dict import advisor_llm

    monkeypatch.setattr(advisor_llm, "describe_columns",
                        lambda result, lang="zh": "- `t.c` — DESC")
    res = _client().post("/api/datadict/generate",
                         json={"catalog_text": CATALOG, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["descriptions"] == "- `t.c` — DESC"


def test_api_health():
    body = _client().get("/api/datadict/health").json()
    assert body == {"status": "ok", "agent": "data_dict"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_datadict_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    demo = ROOT / "examples" / "datadict_demo"
    res = CliRunner().invoke(cli, [
        "datadict", "-f", str(demo / "catalog.json"),
        "--sql-file", str(demo / "workload.sql"), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据字典" in res.output and "gmv" in res.output


def test_cli_min_coverage_gate(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    ddl = tmp_path / "t.sql"
    ddl.write_text(DDL_NO_COMMENTS, encoding="utf-8")
    res = CliRunner().invoke(cli, [
        "datadict", "-f", str(ddl), "--min-coverage", "80"])
    assert res.exit_code == 1
    ok = CliRunner().invoke(cli, [
        "datadict", "-f", str(ddl), "--min-coverage", "10"])
    assert ok.exit_code == 0, ok.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "data_dict" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.data_dict.tools import data_dict

    out = data_dict(CATALOG, sql=WORKLOAD, lang="en")
    assert "Data Dictionary" in out and "gmv" in out
    assert "must not be empty" in data_dict("  ")
    assert "bad input" in data_dict("SELECT 1;")
