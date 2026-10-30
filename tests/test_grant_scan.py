"""Tests for the grant-surface agent (grant_scan).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.grant_scan import (
    render_markdown,
    scan_sql_text,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

SQL = """
CREATE TABLE dw.users (uid BIGINT COMMENT 'id', phone STRING COMMENT '手机号');
GRANT SELECT ON TABLE dw.users TO USER analyst;
GRANT ALL PRIVILEGES ON TABLE dw.orders TO ROLE etl;
GRANT SELECT ON DATABASE dw TO PUBLIC;
GRANT SELECT ON TABLE dw.tmp_scratch TO USER intern;
REVOKE SELECT ON TABLE dw.tmp_scratch FROM USER intern;
"""

CLEAN = """
CREATE TABLE dw.dim_region (rid BIGINT COMMENT 'r');
GRANT SELECT ON TABLE dw.dim_region TO ROLE bi_readers;
"""


# ─────────────────────── scanner ───────────────────────

def test_netting_revoke_cancels_grant():
    r = scan_sql_text(SQL)
    assert r.grants_seen == 4 and r.revokes_seen == 1
    targets = {(g.target, g.principal) for g in r.effective}
    assert ("dw.tmp_scratch", "intern") not in targets
    assert ("dw.users", "analyst") in targets


def test_findings_graded():
    r = scan_sql_text(SQL)
    kinds = {(f.kind, f.target) for f in r.findings}
    assert ("public_grant", "dw") in kinds
    assert ("broad_privilege", "dw.orders") in kinds
    assert ("wide_scope", "dw") in kinds
    sev = {f.kind: f.severity for f in r.findings}
    assert sev["public_grant"] == "high"
    assert sev["broad_privilege"] == "medium"
    assert sev["wide_scope"] == "medium"


def test_sensitive_grant_links_pii():
    # dw.users carries a phone column -> granting it is a high finding
    r = scan_sql_text(SQL)
    hits = [f for f in r.findings if f.kind == "sensitive_grant"]
    assert any(f.target == "dw.users" and f.principal == "analyst"
               and f.severity == "high" for f in hits)
    assert "dw.users" in r.sensitive_tables


def test_clean_surface_reports_clean():
    r = scan_sql_text(CLEAN)
    assert r.counts()["total"] == 0
    assert "干净" in render_markdown(r, "zh")
    assert "clean" in render_markdown(r, "en")


def test_report_orders_by_severity():
    md = render_markdown(scan_sql_text(SQL), "en")
    assert md.index("public grant") < md.index("broad privilege")
    assert "Net grants" in md


# ─────────────────────── CLI ───────────────────────

def test_cli_grants_markdown_json_and_gate():
    res = runner.invoke(cli, ["grants", "--sql", SQL, "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "PUBLIC" in res.output or "public" in res.output

    res = runner.invoke(cli, ["grants", "--sql", SQL, "-F", "json"])
    data = json.loads(res.output)
    assert data["counts"]["high"] >= 2

    res = runner.invoke(cli, ["grants", "--sql", SQL, "--fail-on", "high"])
    assert res.exit_code == 1

    res = runner.invoke(cli, ["grants", "--sql", CLEAN,
                              "--fail-on", "medium"])
    assert res.exit_code == 0, res.output


# ─────────────────────── REST API ───────────────────────

def _api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.grant_scan.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline():
    r = _api_client().post("/api/grants/scan",
                           json={"sql": SQL, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["high"] >= 2
    assert "public grant" in data["report"]


def test_api_requires_input():
    assert _api_client().post("/api/grants/scan",
                              json={}).status_code == 400


# ─────────────────────── MCP / orchestrator wiring ───────────────────────

def test_tool_discovered_everywhere():
    from seatunnel_agent.agents.data.mcp_toolbox.core import (
        build_tool_functions,
    )
    fns = build_tool_functions(include_db=False)
    assert "grant_scan" in fns
    out = fns["grant_scan"](SQL, lang="en")
    assert "public grant" in out
    assert "不能为空" in fns["grant_scan"]("")

    from seatunnel_agent.agents.ai.orchestrator.catalog import build_catalog
    from seatunnel_agent.agents.ai.orchestrator.router import suggest
    cat = build_catalog()
    assert cat["grant_scan"].page == "/grants"
    s = suggest("这个库的授权权限面有没有风险", cat)
    assert s and s[0].tool == "grant_scan"
