"""Tests for the storage-cost agent (45): analyzer, report, API, CLI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from seatunnel_agent.agents.data.storage_cost import (
    render_markdown,
    run_storage_analysis,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "storagecost_demo"
INV = (DEMO / "inventory.csv").read_text("utf-8")
PARTS = (DEMO / "partitions.csv").read_text("utf-8")
TODAY = date(2026, 10, 31)


def _analyze(inv: str = INV, parts: str = PARTS, retention: int = 365):
    return run_storage_analysis(inv, partitions_text=parts,
                                retention_days=retention, today=TODAY)


# ── analyzer ─────────────────────────────────────────────────────────

def test_cold_tier_candidates():
    result = _analyze()
    cold = {a.table: a for a in result.actions if a.kind == "cold_tier"}
    assert set(cold) == {"tmp.backfill_201902", "bak.orders_v1"}
    assert cold["tmp.backfill_201902"].severity == "high"
    assert cold["tmp.backfill_201902"].freed_gb == 2300.0


def test_active_tables_not_cold():
    result = _analyze()
    tables = {a.table for a in result.actions if a.kind == "cold_tier"}
    assert "dwd.orders" not in tables          # accessed daily
    assert "dim.users" not in tables           # too small + active


def test_expired_partitions_counted():
    result = _analyze()
    drops = {a.table: a for a in result.actions
             if a.kind == "drop_partitions"}
    assert drops["ods.click_log"].detail["expired_partitions"] == 2
    assert drops["ods.click_log"].freed_gb == 38.0
    assert drops["ods.click_log"].detail["oldest"] == "dt=2024-09-01"
    assert drops["dwd.orders"].detail["expired_partitions"] == 1


def test_retention_window_respected():
    result = _analyze(retention=30)
    drops = {a.table: a for a in result.actions
             if a.kind == "drop_partitions"}
    # with 30d retention even the 2026-10-30 partitions survive (1 day old)
    assert drops["ods.click_log"].detail["expired_partitions"] == 2
    long = _analyze(retention=3650)
    assert not [a for a in long.actions if a.kind == "drop_partitions"]


def test_small_file_compaction():
    result = _analyze()
    compact = [a for a in result.actions if a.kind == "compact"]
    assert [a.table for a in compact] == ["ods.click_log"]
    assert compact[0].detail["avg_file_mb"] == 4.0


def test_reclaimable_total_and_order():
    result = _analyze()
    assert result.reclaimable_gb == 2300 + 1800 + 38 + 30
    sev = [a.severity for a in result.actions]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_no_partitions_ok():
    result = _analyze(parts="")
    assert not [a for a in result.actions if a.kind == "drop_partitions"]


def test_report_both_langs():
    result = _analyze()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "存储成本治理" in zh and "迁冷存储" in zh
    assert "Storage Cost Governance" in en and "cold tier" in en


def test_clean_report():
    lean = ("table,size_gb,access_cnt_30d,last_access,downstream_cnt\n"
            "t,10,500,2026-10-30,3\n")
    md = render_markdown(_analyze(inv=lean, parts=""), lang="en")
    assert "lean" in md


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.storage_cost import api as sc_api

    app = FastAPI()
    app.include_router(sc_api.router)
    return TestClient(app)


def test_api_analyze_inline():
    res = _client().post("/api/storagecost/analyze",
                         json={"inventory_text": INV,
                               "partitions_text": PARTS,
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["reclaimable_gb"] > 4000
    assert "Storage Cost Governance" in body["report"]


def test_api_bad_inventory_400():
    res = _client().post("/api/storagecost/analyze",
                         json={"inventory_text": "size_gb\n12\n"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("STORAGECOST_API_ALLOWED_DIRS", str(DEMO))
    res = _client().post("/api/storagecost/analyze",
                         json={"inventory_file": str(DEMO / "inventory.csv")})
    assert res.status_code == 200
    bad = _client().post("/api/storagecost/analyze",
                         json={"inventory_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.storage_cost import advisor_llm

    monkeypatch.setattr(advisor_llm, "governance_note",
                        lambda result, lang="zh": "COST-NOTE")
    res = _client().post("/api/storagecost/analyze",
                         json={"inventory_text": INV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["governance_note"] == "COST-NOTE"


def test_api_health():
    body = _client().get("/api/storagecost/health").json()
    assert body == {"status": "ok", "agent": "storage_cost"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_storagecost_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "storagecost", "-f", str(DEMO / "inventory.csv"),
        "--partitions", str(DEMO / "partitions.csv"), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "存储成本治理" in res.output and "tmp.backfill_201902" in res.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "storage_cost" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.storage_cost.tools import storage_cost

    out = storage_cost(INV, partitions=PARTS, lang="en")
    assert "Storage Cost Governance" in out and "bak.orders_v1" in out
    assert "must not be empty" in storage_cost("  ")
    assert "bad input" in storage_cost("size_gb\n12\n")
