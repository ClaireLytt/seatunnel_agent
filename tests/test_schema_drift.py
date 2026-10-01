# -*- coding: utf-8 -*-
"""Tests for the schema drift agent (schema_drift).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.schema_drift import (
    classify_type_change,
    diff_paths,
    diff_scripts,
    load_schemas,
    parse_schema_script,
    render_markdown,
    report_to_dict,
)

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "schema_drift_demo"

OLD = """
CREATE TABLE ods.t (
  id BIGINT COMMENT '主键',
  phone STRING COMMENT '手机号',
  age INT COMMENT '年龄',
  amount DECIMAL(10,2)
) COMMENT '表注释' PARTITIONED BY (dt STRING) STORED AS ORC;
"""

NEW = """
CREATE TABLE ods.t (
  id BIGINT COMMENT '主键',
  age BIGINT COMMENT '年龄',
  amount DECIMAL(16,2),
  email STRING COMMENT '邮箱'
) COMMENT '表注释' PARTITIONED BY (dt STRING) STORED AS ORC;
"""


# ─────────────────────────── parsing ───────────────────────────

def test_parse_schema_script():
    tables, warns = parse_schema_script(OLD)
    assert not warns
    schema = tables["ods.t"]
    assert schema.comment == "表注释"
    assert schema.partition_cols == ["dt"]
    assert schema.columns["phone"].comment == "手机号"
    assert schema.columns["amount"].col_type.startswith("DECIMAL")
    assert schema.columns["dt"].is_partition


def test_parse_error_is_warning():
    tables, warns = parse_schema_script("CREATE TABLE (((")
    assert tables == {}
    assert warns and "解析失败" in warns[0]


def test_load_schemas_dir_and_file(tmp_path):
    (tmp_path / "a.sql").write_text(OLD, encoding="utf-8")
    tables, warns = load_schemas(tmp_path)
    assert "ods.t" in tables and not warns
    tables2, _ = load_schemas(tmp_path / "a.sql")
    assert "ods.t" in tables2


def test_load_schemas_duplicate_definition_warns(tmp_path):
    (tmp_path / "a.sql").write_text(OLD, encoding="utf-8")
    (tmp_path / "b.sql").write_text(OLD, encoding="utf-8")
    _, warns = load_schemas(tmp_path)
    assert any("重复定义" in w for w in warns)


def test_load_schemas_empty_dir(tmp_path):
    tables, warns = load_schemas(tmp_path)
    assert tables == {} and warns


# ─────────────────────────── type classification ───────────────────────────

@pytest.mark.parametrize("old,new,sev", [
    ("INT", "BIGINT", "risk"),
    ("BIGINT", "INT", "breaking"),
    ("FLOAT", "DOUBLE", "risk"),
    ("DOUBLE", "FLOAT", "breaking"),
    ("DECIMAL(10,2)", "DECIMAL(16,2)", "risk"),
    ("DECIMAL(16,2)", "DECIMAL(10,2)", "breaking"),
    ("DECIMAL(10,2)", "DECIMAL(16,4)", "breaking"),  # scale change
    ("VARCHAR(50)", "VARCHAR(100)", "risk"),
    ("VARCHAR(100)", "VARCHAR(50)", "breaking"),
    ("VARCHAR(50)", "STRING", "risk"),
    ("STRING", "INT", "breaking"),
    ("INT", "INT", ""),
])
def test_classify_type_change(old, new, sev):
    assert classify_type_change(old, new) == sev


# ─────────────────────────── diffing ───────────────────────────

def test_diff_scripts_findings():
    report = diff_scripts(OLD, NEW)
    kinds = {(f.kind, f.column): f for f in report.findings}
    assert kinds[("column_removed", "phone")].severity == "breaking"
    assert kinds[("type_changed", "age")].severity == "risk"
    assert kinds[("type_changed", "amount")].severity == "risk"
    assert kinds[("column_added", "email")].severity == "info"


def test_diff_identical_is_clean():
    report = diff_scripts(OLD, OLD)
    assert not report.findings
    assert "未发现" in render_markdown(report, "zh")


def test_diff_detects_rename():
    old = "CREATE TABLE t (uid BIGINT COMMENT 'x');"
    new = "CREATE TABLE t (user_id BIGINT COMMENT 'x');"
    report = diff_scripts(old, new)
    (f,) = report.findings
    assert f.kind == "column_renamed" and f.severity == "risk"
    assert f.old == "uid" and f.new == "user_id"


def test_diff_no_rename_when_type_differs():
    old = "CREATE TABLE t (uid BIGINT);"
    new = "CREATE TABLE t (user_id STRING);"
    report = diff_scripts(old, new)
    kinds = {f.kind for f in report.findings}
    assert kinds == {"column_removed", "column_added"}


def test_diff_partition_change_not_double_reported():
    old = "CREATE TABLE t (id INT) PARTITIONED BY (dt STRING);"
    new = "CREATE TABLE t (id INT) PARTITIONED BY (dt STRING, hour STRING);"
    report = diff_scripts(old, new)
    kinds = [f.kind for f in report.findings]
    assert kinds == ["partition_changed"]
    assert report.findings[0].severity == "breaking"


def test_diff_table_added_and_removed():
    report = diff_scripts("CREATE TABLE a (x INT);",
                          "CREATE TABLE b (x INT);")
    kinds = {f.kind: f for f in report.findings}
    assert kinds["table_removed"].table == "a"
    assert kinds["table_removed"].severity == "breaking"
    assert kinds["table_added"].table == "b"


def test_diff_demo_dirs():
    report = diff_paths(DEMO / "old", DEMO / "new")
    c = report.counts()
    assert c["breaking"] == 3       # phone removed, partition, table removed
    assert c["risk"] == 2           # two widening type changes
    assert c["info"] >= 3


def test_findings_sorted_breaking_first():
    report = diff_scripts(OLD, NEW)
    ranks = [{"info": 1, "risk": 2, "breaking": 3}[f.severity]
             for f in report.findings]
    assert ranks == sorted(ranks, reverse=True)


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    report = diff_scripts(OLD, NEW)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "Schema 漂移检查" in zh and "破坏性变更" in zh
    assert "Schema Drift Check" in en and "Breaking" in en


def test_report_to_dict_messages():
    data = report_to_dict(diff_scripts(OLD, NEW), "en")
    assert all("message" in f for f in data["findings"])
    json.dumps(data)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_schemadiff():
    r = runner.invoke(cli, ["schemadiff", "--old", str(DEMO / "old"),
                            "--new", str(DEMO / "new")])
    assert r.exit_code == 0, r.output
    assert "Schema 漂移检查" in r.output


def test_cli_schemadiff_fail_on(tmp_path):
    out = tmp_path / "drift.json"
    r = runner.invoke(cli, ["schemadiff", "--old", str(DEMO / "old"),
                            "--new", str(DEMO / "new"),
                            "-F", "json", "--fail-on", "breaking",
                            "-o", str(out)])
    assert r.exit_code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["breaking"] >= 1


def test_cli_schemadiff_clean_passes(tmp_path):
    p = tmp_path / "a.sql"
    p.write_text(OLD, encoding="utf-8")
    r = runner.invoke(cli, ["schemadiff", "--old", str(p), "--new", str(p),
                            "--fail-on", "info"])
    assert r.exit_code == 0, r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.schema_drift.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_diff_inline(api_client):
    r = api_client.post("/api/schemadrift/diff", json={
        "old_sql": OLD, "new_sql": NEW, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["breaking"] >= 1
    assert "Schema Drift Check" in data["report"]


def test_api_diff_paths(api_client):
    r = api_client.post("/api/schemadrift/diff", json={
        "old_path": str(DEMO / "old"), "new_path": str(DEMO / "new")})
    assert r.status_code == 200
    assert r.json()["result"]["counts"]["breaking"] == 3


def test_api_diff_path_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("SCHEMADRIFT_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/schemadrift/diff", json={
        "old_path": str(DEMO / "old"), "new_path": str(DEMO / "new")})
    assert r.status_code == 403


def test_api_diff_requires_input(api_client):
    r = api_client.post("/api/schemadrift/diff", json={})
    assert r.status_code == 400
    assert api_client.get("/api/schemadrift/health").json()["status"] == "ok"
