# -*- coding: utf-8 -*-
"""Tests for the SQL formatter (sql_fmt).

Deterministic only — no database, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.sql_fmt import (
    fmt_dir,
    format_text,
    render_batch_markdown,
    render_markdown,
    result_to_dict,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "sqlfmt_demo"

MESSY = ("select a,b , sum(c) as s from t1 join t2 on t1.k=t2.k "
         "where dt='2024-01-01' group by a,b;")


# ─────────────────────────── core formatting ───────────────────────────

def test_format_pretty_prints():
    r = format_text(MESSY)
    assert r.changed and not r.failed
    assert "SELECT\n" in r.formatted
    assert r.formatted.rstrip().endswith(";")


def test_format_is_idempotent():
    once = format_text(MESSY)
    twice = format_text(once.formatted)
    assert not twice.changed


def test_already_formatted_unchanged():
    r = format_text(format_text(MESSY).formatted)
    assert not r.changed
    assert r.diff() == ""


def test_parse_error_kept_verbatim():
    r = format_text("SELECT FROM WHERE;")
    assert r.failed == 1
    assert r.parse_errors
    assert r.formatted == "SELECT FROM WHERE;"
    assert not r.changed


def test_select_star_counted():
    r = format_text("SELECT * FROM t; SELECT a FROM t; SELECT count(*) FROM t;")
    assert r.select_star == 1          # count(*) is not a bare star


def test_multi_statement_split():
    r = format_text("select 1; select 2;")
    assert r.statements == 2
    assert r.formatted.count(";") == 2


def test_diff_is_unified():
    r = format_text(MESSY)
    diff = r.diff()
    assert diff.startswith("---")
    assert "+SELECT" in diff


# ─────────────────────────── directory batch ───────────────────────────

def test_fmt_dir_check_only(tmp_path):
    p = tmp_path / "x.sql"
    p.write_text(MESSY, encoding="utf-8")
    results = fmt_dir(tmp_path, write=False)
    assert results[0].result.changed and not results[0].written
    assert p.read_text(encoding="utf-8") == MESSY   # untouched


def test_fmt_dir_write(tmp_path):
    p = tmp_path / "x.sql"
    p.write_text(MESSY, encoding="utf-8")
    results = fmt_dir(tmp_path, write=True)
    assert results[0].written
    # the written file is now stable
    again = fmt_dir(tmp_path, write=True)
    assert not again[0].result.changed and not again[0].written


def test_fmt_dir_never_writes_failed_files(tmp_path):
    p = tmp_path / "bad.sql"
    original = "SELECT FROM WHERE; select 1;"
    p.write_text(original, encoding="utf-8")
    results = fmt_dir(tmp_path, write=True)
    assert results[0].result.failed == 1
    assert not results[0].written
    assert p.read_text(encoding="utf-8") == original


def test_demo_dir():
    results = fmt_dir(DEMO, write=False)
    (r,) = results
    assert r.result.changed
    assert r.result.select_star == 1


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    r = format_text(MESSY)
    zh = render_markdown(r, "zh")
    en = render_markdown(r, "en")
    assert "SQL 格式化" in zh and "格式化结果" in zh
    assert "SQL Formatter" in en and "Formatted SQL" in en


def test_render_unchanged():
    r = format_text(format_text(MESSY).formatted)
    assert "无需改动" in render_markdown(r, "zh")


def test_render_batch_markdown():
    md = render_batch_markdown(fmt_dir(DEMO), "zh")
    assert "需格式化" in md and "messy.sql" in md


def test_result_to_dict_is_json_serializable():
    json.dumps(result_to_dict(format_text(MESSY)))


# ─────────────────────────── CLI ───────────────────────────

def test_cli_sqlfmt_inline():
    r = runner.invoke(cli, ["sqlfmt", "--sql", MESSY])
    assert r.exit_code == 0, r.output
    assert "SQL 格式化" in r.output


def test_cli_sqlfmt_requires_source():
    r = runner.invoke(cli, ["sqlfmt"])
    assert r.exit_code != 0


def test_cli_sqlfmt_fail_on_change():
    r = runner.invoke(cli, ["sqlfmt", "--sql", MESSY,
                            "--fail-on", "change"])
    assert r.exit_code == 1


def test_cli_sqlfmt_write_then_check(tmp_path):
    p = tmp_path / "x.sql"
    p.write_text(MESSY, encoding="utf-8")
    r = runner.invoke(cli, ["sqlfmt", str(p), "--write"])
    assert r.exit_code == 0, r.output
    r2 = runner.invoke(cli, ["sqlfmt", str(p), "--fail-on", "change"])
    assert r2.exit_code == 0, r2.output


def test_cli_sqlfmt_json():
    r = runner.invoke(cli, ["sqlfmt", "--sql", "select 1", "-F", "json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data[0]["statements"] == 1


def test_cli_sqlfmt_fail_on_error():
    r = runner.invoke(cli, ["sqlfmt", "--sql", "SELECT FROM WHERE;",
                            "--fail-on", "error"])
    assert r.exit_code == 1


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.sql_fmt.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_format(api_client):
    r = api_client.post("/api/sqlfmt/format", json={
        "sql": MESSY, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["changed"] is True
    assert "SELECT" in data["result"]["formatted"]
    assert "SQL Formatter" in data["report"]


def test_api_format_bad_sql_kept(api_client):
    r = api_client.post("/api/sqlfmt/format", json={
        "sql": "SELECT FROM WHERE;"})
    assert r.status_code == 200
    data = r.json()["result"]
    assert data["failed"] == 1 and data["changed"] is False
    assert api_client.get("/api/sqlfmt/health").json()["status"] == "ok"
