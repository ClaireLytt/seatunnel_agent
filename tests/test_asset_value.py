"""Tests for the asset-value agent (44): valuer, report, API, CLI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from seatunnel_agent.agents.data.asset_value import (
    parse_inventory,
    render_markdown,
    value_assets,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "assetvalue_demo" / "inventory.csv"
CSV = DEMO.read_text("utf-8")
TODAY = date(2026, 10, 31)


def _grade(text: str = CSV):
    return value_assets(parse_inventory(text), today=TODAY)


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_csv_and_json_equivalent():
    import json

    rows_csv = parse_inventory(CSV)
    as_json = json.dumps([r.to_dict() for r in rows_csv])
    rows_json = parse_inventory(as_json)
    assert [r.table for r in rows_json] == [r.table for r in rows_csv]


def test_parse_rejects_bad_rows():
    import pytest

    with pytest.raises(ValueError):
        parse_inventory("   ")
    with pytest.raises(ValueError):
        parse_inventory("size_gb\n12\n")           # no table column
    with pytest.raises(ValueError):
        parse_inventory("table,size_gb\nt1,notnum\n")


# ── grading ──────────────────────────────────────────────────────────

def test_tiers_and_order():
    result = _grade()
    assert result.assets[0].score >= result.assets[-1].score
    by_name = {a.table: a for a in result.assets}
    assert by_name["dim.users"].tier == "core"
    assert by_name["tmp.backfill_201902"].tier == "idle"
    assert by_name["bak.orders_v1"].tier == "idle"


def test_quadrants_split_on_median():
    result = _grade()
    by_name = {a.table: a for a in result.assets}
    assert by_name["dim.users"].quadrant == "core-light"
    assert by_name["dwd.orders"].quadrant == "core-heavy"
    assert by_name["tmp.backfill_201902"].quadrant == "idle-heavy"


def test_score_components_capped():
    result = value_assets(parse_inventory(
        "table,size_gb,access_cnt_30d,last_access,downstream_cnt\n"
        "t,1,1000000,2026-10-31,100\n"), today=TODAY)
    ev = result.assets[0].evidence
    assert ev["access_pts"] == 50.0
    assert ev["deps_pts"] == 30.0
    assert ev["recency_pts"] == 20.0
    assert result.assets[0].score == 100.0


def test_missing_last_access_scores_zero_recency():
    result = value_assets(parse_inventory(
        "table,size_gb,access_cnt_30d,last_access,downstream_cnt\n"
        "t,1,10,,0\n"), today=TODAY)
    assert result.assets[0].evidence["recency_pts"] == 0.0
    assert result.assets[0].evidence["days_since_access"] is None


def test_tier_counts():
    result = _grade()
    assert sum(result.tiers.values()) == 8
    assert result.tiers["idle"] == 2


def test_report_both_langs():
    result = _grade()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据资产价值评估" in zh and "低价值·高成本" in zh
    assert "Asset Value Grading" in en and "storagecost" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.asset_value import api as av_api

    app = FastAPI()
    app.include_router(av_api.router)
    return TestClient(app)


def test_api_grade_inline():
    res = _client().post("/api/assetvalue/grade",
                         json={"inventory_text": CSV, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["assets"]) == 8
    assert "Asset Value Grading" in body["report"]


def test_api_bad_inventory_400():
    res = _client().post("/api/assetvalue/grade",
                         json={"inventory_text": "size_gb\n12\n"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("ASSETVALUE_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/assetvalue/grade",
                         json={"inventory_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/assetvalue/grade",
                         json={"inventory_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.asset_value import advisor_llm

    monkeypatch.setattr(advisor_llm, "grading_note",
                        lambda result, lang="zh": "GRADE-NOTE")
    res = _client().post("/api/assetvalue/grade",
                         json={"inventory_text": CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["grading_note"] == "GRADE-NOTE"


def test_api_health():
    body = _client().get("/api/assetvalue/health").json()
    assert body == {"status": "ok", "agent": "asset_value"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_assetvalue_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "assetvalue", "-f", str(DEMO), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据资产价值评估" in res.output and "tmp.backfill_201902" in res.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "asset_value" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.asset_value.tools import asset_value

    out = asset_value(CSV, lang="en")
    assert "Asset Value Grading" in out and "bak.orders_v1" in out
    assert "must not be empty" in asset_value("  ")
    assert "bad input" in asset_value("size_gb\n12\n")
