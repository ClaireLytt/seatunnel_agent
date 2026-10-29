"""Tests for the masking-SQL generator (pii_scan.masker).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from seatunnel_agent.agents.data.pii_scan import (
    mask_expression,
    plan_sql_text,
    render_mask_sql,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

DDL = """
CREATE TABLE ods.user_info (
  user_id BIGINT COMMENT '用户ID',
  phone STRING COMMENT '手机号',
  id_card_no STRING COMMENT '身份证号',
  email STRING COMMENT '邮箱',
  salary DOUBLE COMMENT '工资',
  note STRING COMMENT '备注'
) PARTITIONED BY (dt STRING COMMENT '分区日期') STORED AS ORC;
"""

LINEAGE_ONLY = DDL + """
INSERT INTO dw.user_wide
SELECT user_id, phone, id_card_no FROM ods.user_info;
"""


# ─────────────────────── expressions ───────────────────────

def test_mask_expression_per_category():
    assert mask_expression("phone", "phone") == \
        "concat(substr(phone, 1, 3), '****', substr(phone, -4))"
    assert "substr(id_card_no, 1, 6)" in mask_expression("id_card", "id_card_no")
    assert mask_expression("salary", "salary", "double") == "cast(null as double)"
    # unknown / custom categories hash instead of guessing a truncation
    assert mask_expression("wechat", "wechat_id") == "md5(cast(wechat_id as string))"


def test_mask_expression_salary_defaults_to_string_type():
    assert mask_expression("salary", "salary") == "cast(null as string)"


# ─────────────────────── plan from DDL ───────────────────────

def test_plan_builds_full_view_in_ddl_order():
    plan = plan_sql_text(DDL)
    assert [t.table for t in plan.tables] == ["ods.user_info"]
    t = plan.tables[0]
    assert t.view_name == "ods.user_info_masked"
    # every DDL column survives, in order
    assert t.columns == ["user_id", "phone", "id_card_no",
                         "email", "salary", "note", "dt"]
    assert {m.column for m in t.masked} == {"phone", "id_card_no",
                                            "email", "salary"}
    # untouched columns pass through bare; flagged ones carry AS + marker
    assert "\n  user_id,\n" in t.view_sql
    assert "AS phone  -- phone · high" in t.view_sql
    assert t.view_sql.endswith("FROM ods.user_info;")


def test_plan_lineage_only_table_degrades_to_expressions():
    plan = plan_sql_text(LINEAGE_ONLY)
    tables = {t.table for t in plan.tables}
    assert "dw.user_wide" not in tables          # no DDL -> no view
    exprs = {(m.table, m.column) for m in plan.expressions_only}
    assert ("dw.user_wide", "phone") in exprs
    assert any("dw.user_wide" in w for w in plan.warnings)


def test_plan_min_confidence_skips_weak_hits():
    ddl = "CREATE TABLE t (name STRING COMMENT 'nickname');"
    loose = plan_sql_text(ddl, min_confidence="low")
    strict = plan_sql_text(ddl, min_confidence="high")
    assert any(m.column == "name"
               for t in loose.tables for m in t.masked)
    assert not strict.tables
    assert strict.skipped and strict.skipped[0]["column"] == "name"


def test_render_mask_sql_is_executable_shaped():
    sql = render_mask_sql(plan_sql_text(LINEAGE_ONLY))
    assert sql.count("CREATE OR REPLACE VIEW") == 1
    assert "FROM ods.user_info;" in sql
    assert "dw.user_wide.phone" in sql            # expression-only section
    assert sql.startswith("--")


def test_plan_to_dict_counts():
    d = plan_sql_text(LINEAGE_ONLY).to_dict()
    assert d["counts"]["views"] == 1
    assert d["counts"]["masked_columns"] >= 4
    assert d["counts"]["expressions_only"] >= 2


# ─────────────────────── coverage (verification) ───────────────────────

def test_coverage_full_when_every_table_has_ddl():
    cov = plan_sql_text(DDL).coverage
    assert cov.findings_total == cov.covered > 0
    assert cov.uncovered == []
    assert cov.unmasked_edges_after == 0
    assert cov.worst_uncovered() is None


def test_coverage_counts_no_ddl_findings_as_uncovered():
    cov = plan_sql_text(LINEAGE_ONLY).coverage
    assert cov.covered < cov.findings_total
    reasons = {u.reason for u in cov.uncovered}
    assert reasons == {"no_ddl"}
    assert cov.worst_uncovered() == "high"


def test_coverage_counts_skipped_weak_hits_as_uncovered():
    ddl = "CREATE TABLE t (name STRING COMMENT 'nickname');"
    cov = plan_sql_text(ddl, min_confidence="high").coverage
    assert cov.covered == 0
    assert cov.uncovered[0].reason == "below_min_confidence"


def test_coverage_in_rendered_sql_and_dict():
    sql = render_mask_sql(plan_sql_text(LINEAGE_ONLY))
    assert "覆盖回验 coverage:" in sql
    assert "UNCOVERED dw.user_wide.phone" in sql
    d = plan_sql_text(LINEAGE_ONLY).to_dict()
    assert d["coverage"]["findings_total"] == d["coverage"]["covered"] \
        + len(d["coverage"]["uncovered"])


# ─────────────────────── CLI surface ───────────────────────

def test_cli_pii_mask_flag_outputs_sql():
    res = runner.invoke(cli, ["pii", "--sql", DDL, "--mask"])
    assert res.exit_code == 0, res.output
    assert "CREATE OR REPLACE VIEW ods.user_info_masked" in res.output


def test_cli_pii_mask_json():
    res = runner.invoke(cli, ["pii", "--sql", DDL, "--mask", "-F", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["counts"]["views"] == 1
    assert data["tables"][0]["view_name"] == "ods.user_info_masked"


def test_cli_pii_mask_gate_passes_when_covered():
    # all findings get a view -> treatment-aware gate is satisfied
    res = runner.invoke(cli, ["pii", "--sql", DDL, "--mask",
                              "--fail-on", "high"])
    assert res.exit_code == 0, res.output


def test_cli_pii_mask_gate_fails_on_uncovered():
    # dw.user_wide is lineage-only (no DDL) -> its high finding is uncovered
    res = runner.invoke(cli, ["pii", "--sql", LINEAGE_ONLY, "--mask",
                              "--fail-on", "high"])
    assert res.exit_code == 1


# ─────────────────────── REST API ───────────────────────

def _api_client():
    import pytest

    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.pii_scan.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_mask_inline():
    r = _api_client().post("/api/pii/mask", json={"sql": DDL})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["views"] == 1
    assert "CREATE OR REPLACE VIEW ods.user_info_masked" in data["sql"]


def test_api_mask_min_confidence_validated():
    r = _api_client().post("/api/pii/mask",
                           json={"sql": DDL, "min_confidence": "medium"})
    assert r.status_code == 400


def test_api_mask_requires_input():
    r = _api_client().post("/api/pii/mask", json={})
    assert r.status_code == 400
