"""Tests for the data-contract agent (contract_check).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.contract_check import (
    check_sql_text,
    parse_contract,
    render_markdown,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

CONTRACT = """
tables:
  - name: dwd.orders
    columns:
      - { name: order_id, type: bigint }
      - { name: amount, type: decimal, comment: true }
      - { name: buyer_id }
    partitioned_by: [dt]
  - name: dwd.payments
    columns: [pay_id]
"""

DDL = """
CREATE TABLE dwd.orders (
  order_id STRING COMMENT 'id',
  amount DECIMAL(16,2),
  extra_col INT COMMENT 'x'
) PARTITIONED BY (ds STRING COMMENT 'p');
"""

CLEAN_DDL = """
CREATE TABLE dwd.orders (
  order_id BIGINT COMMENT 'id',
  amount DECIMAL(16,2) COMMENT 'paid',
  buyer_id BIGINT COMMENT 'buyer'
) PARTITIONED BY (dt STRING COMMENT 'p');
CREATE TABLE dwd.payments (pay_id BIGINT COMMENT 'pid');
"""


# ─────────────────────── contract parsing ───────────────────────

def test_parse_contract_shapes():
    tcs = parse_contract(CONTRACT)
    assert [t.name for t in tcs] == ["dwd.orders", "dwd.payments"]
    orders = tcs[0]
    assert orders.partitioned_by == ["dt"]
    assert orders.columns[1].col_type == "decimal"
    assert orders.columns[1].comment is True
    assert orders.columns[2].col_type == ""       # bare name = any type
    assert tcs[1].columns[0].name == "pay_id"     # string shorthand


@pytest.mark.parametrize("bad", [
    "not: yaml: [", "{}", "tables: {}", "tables: [{columns: []}]",
    "tables: [{name: t, partitioned_by: dt}]",
])
def test_parse_contract_rejects_bad_shapes(bad):
    with pytest.raises(ValueError):
        parse_contract(bad)


# ─────────────────────── checker ───────────────────────

def test_violations_graded():
    r = check_sql_text(DDL, contract=CONTRACT)
    kinds = {(f.kind, f.table, f.column) for f in r.findings}
    assert ("missing_table", "dwd.payments", "") in kinds       # high
    assert ("type_mismatch", "dwd.orders", "order_id") in kinds  # high
    assert ("missing_column", "dwd.orders", "buyer_id") in kinds
    assert ("partition_mismatch", "dwd.orders", "") in kinds     # medium
    assert ("missing_comment", "dwd.orders", "amount") in kinds  # low
    sev = {f.kind: f.severity for f in r.findings}
    assert sev["missing_table"] == "high"
    assert sev["partition_mismatch"] == "medium"
    assert sev["missing_comment"] == "low"
    assert r.tables_declared == 2 and r.tables_checked == 1


def test_type_prefix_matches_parameterized():
    # `decimal` in the contract accepts DECIMAL(16,2)
    r = check_sql_text(DDL, contract=CONTRACT)
    assert not any(f.kind == "type_mismatch" and f.column == "amount"
                   for f in r.findings)


def test_extra_columns_only_when_disallowed():
    r = check_sql_text(DDL, contract=CONTRACT)
    assert not any(f.kind == "extra_column" for f in r.findings)
    strict = CONTRACT.replace("partitioned_by: [dt]",
                              "partitioned_by: [dt]\n"
                              "    allow_extra_columns: false")
    r2 = check_sql_text(DDL, contract=strict)
    extras = {f.column for f in r2.findings if f.kind == "extra_column"}
    assert extras == {"extra_col"}


def test_require_comments_covers_undeclared_columns():
    contract = """
tables:
  - name: dwd.orders
    require_comments: true
"""
    r = check_sql_text(DDL, contract=contract)
    missing = {f.column for f in r.findings if f.kind == "missing_comment"}
    assert "amount" in missing and "order_id" not in missing


def test_clean_ddl_honors_contract():
    r = check_sql_text(CLEAN_DDL, contract=CONTRACT)
    assert r.counts()["total"] == 0
    assert "没有违约项" in render_markdown(r, "zh")
    assert "no violations" in render_markdown(r, "en")


def test_report_orders_by_severity():
    md = render_markdown(check_sql_text(DDL, contract=CONTRACT), "en")
    assert md.index("missing table") < md.index("partition violation")
    assert md.index("partition violation") < md.index("missing comment")


# ─────────────────────── CLI ───────────────────────

def _write_contract(tmp_path) -> str:
    p = tmp_path / "contract.yaml"
    p.write_text(CONTRACT, encoding="utf-8")
    return str(p)


def test_cli_contract_markdown_json_and_gate(tmp_path):
    cpath = _write_contract(tmp_path)
    res = runner.invoke(cli, ["contract", "--sql", DDL, "-c", cpath,
                              "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "dwd.payments" in res.output

    res = runner.invoke(cli, ["contract", "--sql", DDL, "-c", cpath,
                              "-F", "json"])
    data = json.loads(res.output)
    assert data["counts"]["high"] >= 2

    res = runner.invoke(cli, ["contract", "--sql", DDL, "-c", cpath,
                              "--fail-on", "high"])
    assert res.exit_code == 1

    res = runner.invoke(cli, ["contract", "--sql", CLEAN_DDL, "-c", cpath,
                              "--fail-on", "low"])
    assert res.exit_code == 0, res.output


def test_cli_contract_rejects_bad_contract(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("tables: {}", encoding="utf-8")
    res = runner.invoke(cli, ["contract", "--sql", DDL, "-c", str(p)])
    assert res.exit_code != 0
    assert "契约格式错误" in res.output


# ─────────────────────── bootstrap (--init) ───────────────────────

def test_init_round_trips_clean():
    from seatunnel_agent.agents.data.contract_check.bootstrap import (
        generate_contract,
    )
    draft = generate_contract(CLEAN_DDL)
    # the generated draft parses and the same DDL honors it in full
    r = check_sql_text(CLEAN_DDL, contract=draft)
    assert r.counts()["total"] == 0
    # commented columns become comment requirements, partitions declared
    assert "comment: true" in draft
    assert "partitioned_by: [dt]" in draft


def test_init_rejects_ddl_free_input():
    from seatunnel_agent.agents.data.contract_check.bootstrap import (
        generate_contract,
    )
    with pytest.raises(ValueError):
        generate_contract("SELECT 1;")


def test_cli_contract_init(tmp_path):
    out = tmp_path / "contract.yaml"
    res = runner.invoke(cli, ["contract", "--init", "--sql", CLEAN_DDL,
                              "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert "tables:" in res.output
    # the saved draft gates the same DDL clean end to end
    res2 = runner.invoke(cli, ["contract", "--sql", CLEAN_DDL,
                               "-c", str(out), "--fail-on", "low"])
    assert res2.exit_code == 0, res2.output


def test_cli_contract_requires_c_or_init():
    res = runner.invoke(cli, ["contract", "--sql", CLEAN_DDL])
    assert res.exit_code != 0
    assert "--init" in res.output


# ─────────────────────── REST API ───────────────────────

def _api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.contract_check.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline():
    r = _api_client().post("/api/contract/scan",
                           json={"sql": DDL, "contract": CONTRACT,
                                 "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["high"] >= 2
    assert "missing table" in data["report"]


def test_api_contract_is_required():
    r = _api_client().post("/api/contract/scan", json={"sql": DDL})
    assert r.status_code == 422          # pydantic: contract is required


def test_api_bad_contract_structured():
    r = _api_client().post("/api/contract/scan",
                           json={"sql": DDL, "contract": "tables: {}"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "contract_failed"


def test_api_requires_input():
    r = _api_client().post("/api/contract/scan",
                           json={"contract": CONTRACT})
    assert r.status_code == 400


# ─────────────────────── history / stats ───────────────────────

def test_history_logged_and_stats_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cpath = _write_contract(tmp_path)
    res = runner.invoke(cli, ["contract", "--sql", DDL, "-c", cpath])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "logs" / "contract.jsonl").exists()

    client = _api_client()
    client.post("/api/contract/scan",
                json={"sql": DDL, "contract": CONTRACT})
    r = client.get("/api/contract/stats")
    assert r.status_code == 200
    records = r.json()["records"]
    assert {rec["source"] for rec in records} == {"cli", "api"}
    assert records[-1]["tables_declared"] == 2


# ─────────────────────── MCP / orchestrator wiring ───────────────────────

def test_tool_discovered_everywhere():
    from seatunnel_agent.agents.data.mcp_toolbox.core import (
        build_tool_functions,
    )
    fns = build_tool_functions(include_db=False)
    assert "contract_check" in fns
    out = fns["contract_check"](DDL, CONTRACT, lang="en")
    assert "missing table" in out
    assert "不能为空" in fns["contract_check"]("", CONTRACT)
    assert "bad contract" in fns["contract_check"](DDL, "tables: {}")

    from seatunnel_agent.agents.ai.orchestrator.catalog import build_catalog
    from seatunnel_agent.agents.ai.orchestrator.router import suggest
    cat = build_catalog()
    assert cat["contract_check"].page == "/contract"
    s = suggest("帮我校验数据契约", cat)
    assert s and s[0].tool == "contract_check"


def test_diff_surfaces_reverse_drift(tmp_path):
    from seatunnel_agent.agents.data.contract_check.bootstrap import (
        diff_contract,
        generate_contract,
    )
    grown = CLEAN_DDL + (
        "\nCREATE TABLE dwd.newcomer (x BIGINT COMMENT 'x');\n")
    drift = diff_contract(CONTRACT, grown)
    assert drift["new_tables"] == ["dwd.newcomer"]
    # a new physical column on a table with typed promises surfaces too
    grown2 = CLEAN_DDL.replace(
        "buyer_id BIGINT COMMENT 'buyer'",
        "buyer_id BIGINT COMMENT 'buyer',\n  channel STRING COMMENT 'c'")
    drift2 = diff_contract(CONTRACT, grown2)
    assert drift2["new_columns"] == ["dwd.orders.channel"]
    # the bootstrap round-trip has no reverse drift by construction
    clean = diff_contract(generate_contract(CLEAN_DDL), CLEAN_DDL)
    assert clean == {"new_tables": [], "new_columns": []}


def test_cli_contract_diff_gate(tmp_path):
    cpath = _write_contract(tmp_path)
    grown = CLEAN_DDL + "\nCREATE TABLE dwd.newcomer (x BIGINT COMMENT 'x');"
    res = runner.invoke(cli, ["contract", "--diff", "--sql", grown,
                              "-c", cpath, "-F", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["new_tables"] == ["dwd.newcomer"]

    res = runner.invoke(cli, ["contract", "--diff", "--sql", grown,
                              "-c", cpath, "--fail-on", "high"])
    assert res.exit_code == 1

    res = runner.invoke(cli, ["contract", "--diff", "--sql", CLEAN_DDL,
                              "-c", cpath])
    assert res.exit_code == 0, res.output
