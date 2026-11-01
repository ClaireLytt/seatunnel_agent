"""Tests for the coverage_map agent (mapper / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.coverage_map import (
    map_coverage,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "coveragemap_demo"


def _demo_map():
    return map_coverage(
        (DEMO / "warehouse.sql").read_text(encoding="utf-8"),
        rules_text=(DEMO / "rules.yaml").read_text(encoding="utf-8"),
        contract_text=(DEMO / "contract.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ mapper

def test_demo_map_and_coverage_share():
    cmap = _demo_map()
    assert cmap.covered == 2 and len(cmap.tables) == 4
    assert cmap.coverage_share == 0.5
    by = {t.table: t for t in cmap.tables}
    assert by["dwd.orders"].checks["row_count"] == 1
    assert by["dwd.orders"].checks["unique"] == 1
    assert by["dim.users"].contract and by["dim.users"].covered
    assert not by["dws.orders_daily"].covered
    assert cmap.tables[0].covered is False          # unprotected first


def test_findings_graded_by_layer_and_dead_gate():
    cmap = _demo_map()
    by = {(f.code, f.table): f for f in cmap.findings}
    assert by[("CM001", "dws.orders_daily")].severity == "high"   # hot
    assert by[("CM001", "tmp.scratch")].severity == "medium"
    assert by[("CM002", "ods.legacy_gone")].detail == "dqc"


def test_contract_only_and_rules_only():
    ddl = (DEMO / "warehouse.sql").read_text(encoding="utf-8")
    rules_only = map_coverage(
        ddl, rules_text=(DEMO / "rules.yaml").read_text(encoding="utf-8"))
    assert rules_only.covered == 1
    contract_only = map_coverage(
        ddl,
        contract_text=(DEMO / "contract.yaml").read_text(encoding="utf-8"))
    assert contract_only.covered == 1


def test_dead_contract_gate():
    ddl = "CREATE TABLE a.t (x INT)"
    contract = "tables:\n  - name: b.gone\n    columns:\n      - name: x\n"
    cmap = map_coverage(ddl, contract_text=contract)
    (f,) = [f for f in cmap.findings if f.code == "CM002"]
    assert f.table == "b.gone" and f.detail == "contract"


def test_bad_inputs():
    ddl = "CREATE TABLE a.t (x INT)"
    with pytest.raises(ValueError, match="at least one gate"):
        map_coverage(ddl)
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        map_coverage("SELECT 1", rules_text="version: 1\nrules: []\n")
    with pytest.raises(ValueError, match="rules YAML"):
        map_coverage(ddl, rules_text="version: 1\nrules:\n  - checks: []\n")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    cmap = _demo_map()
    zh = render_markdown(cmap, lang="zh")
    en = render_markdown(cmap, lang="en")
    assert "质量覆盖地图" in zh and "裸奔" in zh
    assert "Coverage Map" in en and "dead gate" in en
    clean = map_coverage(
        "CREATE TABLE a.t (x INT)",
        rules_text="version: 1\nrules:\n  - table: a.t\n    checks:\n"
                   "      - type: row_count\n        min: 1\n")
    out = render_markdown(clean, lang="en")
    assert "at least one gate" in out


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["coveragemap", "--ddl", str(DEMO / "warehouse.sql"),
            "--rules", str(DEMO / "rules.yaml"),
            "--contract", str(DEMO / "contract.yaml")]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "质量覆盖地图" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"coverage_share": 0.5' in res.output
    res = runner.invoke(cli, args + ["--fail-on-high"])
    assert res.exit_code == 1 and "dws.orders_daily" in res.output


def test_cli_requires_an_artifact():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["coveragemap", "--ddl",
                                   str(DEMO / "warehouse.sql")])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.coverage_map.tools import coverage_map

    out = coverage_map(
        (DEMO / "warehouse.sql").read_text(encoding="utf-8"),
        rules=(DEMO / "rules.yaml").read_text(encoding="utf-8"),
        lang="en")
    assert "Coverage Map" in out and "CM001" in out
    assert "must not be empty" in coverage_map("  ")
    assert "bad input" in coverage_map("CREATE TABLE a.t (x INT)")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.coverage_map.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_map_and_health():
    client = _client()
    assert client.get("/api/coveragemap/health").status_code == 200
    resp = client.post("/api/coveragemap/map", json={
        "ddl_text": (DEMO / "warehouse.sql").read_text(encoding="utf-8"),
        "rules_text": (DEMO / "rules.yaml").read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["covered"] == 1
    assert "Coverage Map" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/coveragemap/map", json={
        "ddl_text": "CREATE TABLE a.t (x INT)"})
    assert resp.status_code == 400
