"""Tests for the asset-search agent (42): searcher, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.asset_search import (
    parse_catalog,
    render_markdown,
    search_assets,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "assetsearch_demo" / "catalog.json"
CATALOG = DEMO.read_text("utf-8")

DDL = """
CREATE TABLE dwd.orders (
  order_id BIGINT COMMENT '订单号',
  amount DECIMAL(18,2) COMMENT '订单金额'
) COMMENT '订单明细';
CREATE EXTERNAL TABLE IF NOT EXISTS dim.users (
  user_id STRING COMMENT '用户ID'
);
"""


def _search(query: str, catalog: str = CATALOG, limit: int = 10):
    return search_assets(parse_catalog(catalog), query, limit=limit)


# ── parsing ──────────────────────────────────────────────────────────

def test_parse_json_catalog():
    assets = parse_catalog(CATALOG)
    assert len(assets) == 5
    assert assets[0].table == "dws.orders_daily"
    assert assets[0].columns[3]["name"] == "gmv"


def test_parse_ddl_catalog():
    assets = parse_catalog(DDL)
    names = {a.table for a in assets}
    assert names == {"dwd.orders", "dim.users"}
    orders = next(a for a in assets if a.table == "dwd.orders")
    assert orders.comment == "订单明细"
    assert orders.columns[1] == {"name": "amount", "comment": "订单金额"}


def test_parse_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        parse_catalog("   ")
    with pytest.raises(ValueError):
        parse_catalog("SELECT 1;")
    with pytest.raises(ValueError):
        parse_catalog('[{"no_table": 1}]')


# ── search ───────────────────────────────────────────────────────────

def test_chinese_query_ranks_daily_summary_first():
    result = _search("按日的订单金额汇总")
    assert result.hits[0].table == "dws.orders_daily"
    assert "gmv" in result.hits[0].matched_columns


def test_english_query_with_synonyms():
    result = _search("daily order amount")
    assert result.hits[0].table == "dws.orders_daily"


def test_synonym_bridges_zh_to_en_columns():
    # “留存” should land on the retention table via the synonym bridge
    result = _search("用户留存")
    assert result.hits[0].table == "dws.user_retention_weekly"


def test_no_hits_for_unrelated_query():
    result = _search("kubernetes pods")
    assert result.hits == []
    md = render_markdown(result, lang="en")
    assert "Nothing matched" in md


def test_limit_respected():
    result = _search("订单", limit=1)
    assert len(result.hits) == 1


def test_empty_query_raises():
    import pytest

    with pytest.raises(ValueError):
        _search("   ")


def test_report_both_langs():
    result = _search("订单金额")
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数据资产搜索" in zh and "dws.orders_daily" in zh
    assert "Asset Search" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.asset_search import api as as_api

    app = FastAPI()
    app.include_router(as_api.router)
    return TestClient(app)


def test_api_search_inline():
    res = _client().post("/api/assetsearch/search",
                         json={"catalog_text": CATALOG,
                               "query": "按日的订单金额",
                               "report": True, "lang": "zh"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["hits"][0]["table"] == "dws.orders_daily"
    assert "数据资产搜索" in body["report"]


def test_api_bad_catalog_400():
    res = _client().post("/api/assetsearch/search",
                         json={"catalog_text": "SELECT 1;", "query": "x"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("ASSETSEARCH_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/assetsearch/search",
                         json={"catalog_file": str(DEMO), "query": "订单"})
    assert res.status_code == 200
    bad = _client().post("/api/assetsearch/search",
                         json={"catalog_file": str(ROOT / "pyproject.toml"),
                               "query": "订单"})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.asset_search import advisor_llm

    monkeypatch.setattr(advisor_llm, "recommend_note",
                        lambda result, lang="zh": "PICK dws.orders_daily")
    res = _client().post("/api/assetsearch/search",
                         json={"catalog_text": CATALOG, "query": "订单",
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["recommendation"] == "PICK dws.orders_daily"


def test_api_health():
    body = _client().get("/api/assetsearch/health").json()
    assert body == {"status": "ok", "agent": "asset_search"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_assetsearch_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "assetsearch", "-f", str(DEMO), "-q", "按日的订单金额",
        "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据资产搜索" in res.output and "dws.orders_daily" in res.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "asset_search" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.asset_search.tools import asset_search

    out = asset_search(CATALOG, "订单金额", lang="zh")
    assert "数据资产搜索" in out and "dws.orders_daily" in out
    assert "must not be empty" in asset_search("  ", "x")
    assert "must not be empty" in asset_search(CATALOG, " ")
    assert "bad input" in asset_search("SELECT 1;", "订单")
