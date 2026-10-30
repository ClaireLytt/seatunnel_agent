"""Tests for the metadata-quality agent (metadata_quality).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.metadata_quality import (
    check_sql_text,
    render_markdown,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

SQL = """
CREATE TABLE ods.user_log (
  uid BIGINT COMMENT 'id',
  pay_amount DOUBLE,
  birth_date STRING COMMENT 'birth'
) PARTITIONED BY (dt STRING COMMENT 'p');
CREATE TABLE dwd.ods_leftover (oid BIGINT COMMENT 'order');
"""

CLEAN = """
CREATE TABLE ods.user_log (
  uid BIGINT COMMENT 'id',
  pay_amount DECIMAL(16,2) COMMENT 'paid'
) PARTITIONED BY (dt STRING COMMENT 'p');
"""


# ─────────────────────── checker ───────────────────────

def test_money_float_is_high():
    r = check_sql_text(SQL)
    hits = [f for f in r.findings if f.kind == "money_float"]
    assert len(hits) == 1
    assert hits[0].severity == "high"
    assert hits[0].column == "pay_amount"


def test_missing_comment_and_coverage():
    r = check_sql_text(SQL)
    missing = {(f.table, f.column) for f in r.findings
               if f.kind == "missing_comment"}
    assert ("ods.user_log", "pay_amount") in missing
    cov = {c.table: c.pct for c in r.coverage}
    assert cov["ods.user_log"] == 75          # 3 of 4 (dt counts, commented)
    assert cov["dwd.ods_leftover"] == 100


def test_date_string_flagged_partition_exempt():
    r = check_sql_text(SQL)
    dates = {f.column for f in r.findings if f.kind == "date_string"}
    assert dates == {"birth_date"}            # dt is a partition column


def test_layer_naming_only_cross_layer_mismatch():
    r = check_sql_text(SQL)
    layer = [f for f in r.findings if f.kind == "layer_naming"]
    assert [f.table for f in layer] == ["dwd.ods_leftover"]
    # unprefixed tables inside a layered db are a style, not a finding
    assert not any(f.table == "ods.user_log" for f in layer)


def test_unpartitioned_fact_only_dwd_dws():
    sql = """
    CREATE TABLE dwd.fact_orders (oid BIGINT COMMENT 'o');
    CREATE TABLE dws.agg_daily (d BIGINT COMMENT 'd');
    CREATE TABLE dim.dim_user (uid BIGINT COMMENT 'u');
    CREATE TABLE ods.raw_log (line STRING COMMENT 'l');
    CREATE TABLE dwd.fact_ok (oid BIGINT COMMENT 'o')
      PARTITIONED BY (dt STRING COMMENT 'p');
    """
    r = check_sql_text(sql)
    hits = {f.table for f in r.findings if f.kind == "unpartitioned_fact"}
    # dim/ods stay silent; a partitioned dwd table passes
    assert hits == {"dwd.fact_orders", "dws.agg_daily"}
    assert all(f.severity == "medium" for f in r.findings
               if f.kind == "unpartitioned_fact")


def test_money_string_is_medium():
    sql = ("CREATE TABLE t (pay_amount STRING COMMENT 'a', "
           "note STRING COMMENT 'n');")
    r = check_sql_text(sql)
    hits = [f for f in r.findings if f.kind == "money_string"]
    assert [(f.column, f.severity) for f in hits] == [
        ("pay_amount", "medium")]


def test_clean_ddl_reports_clean():
    r = check_sql_text(CLEAN)
    assert r.counts()["total"] == 0
    assert "干净" in render_markdown(r, "zh")
    assert "clean" in render_markdown(r, "en")


def test_report_orders_by_severity():
    md = render_markdown(check_sql_text(SQL), "en")
    assert md.index("money on float") < md.index("missing comment")


# ─────────────────────── CLI ───────────────────────

def test_cli_metaquality_markdown_json_and_gate():
    res = runner.invoke(cli, ["metaquality", "--sql", SQL, "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "pay_amount" in res.output

    res = runner.invoke(cli, ["metaquality", "--sql", SQL, "-F", "json"])
    data = json.loads(res.output)
    assert data["counts"]["high"] == 1

    res = runner.invoke(cli, ["metaquality", "--sql", SQL,
                              "--fail-on", "high"])
    assert res.exit_code == 1

    res = runner.invoke(cli, ["metaquality", "--sql", CLEAN,
                              "--fail-on", "low"])
    assert res.exit_code == 0, res.output


# ─────────────────────── history ───────────────────────

def test_history_logged_and_stats_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(cli, ["metaquality", "--sql", SQL])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "logs" / "metaquality.jsonl").exists()

    res = runner.invoke(cli, ["metaquality-stats"])
    assert res.exit_code == 0, res.output
    assert "注释覆盖" in res.output and "趋势" in res.output


# ─────────────────────── REST API ───────────────────────

def _api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.metadata_quality.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline():
    r = _api_client().post("/api/metaquality/scan",
                           json={"sql": SQL, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["high"] == 1
    assert "DECIMAL" in data["report"]


def test_api_requires_input():
    assert _api_client().post("/api/metaquality/scan",
                              json={}).status_code == 400
