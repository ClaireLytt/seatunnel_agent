"""Tests for the layer-check agent (55): checker, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.layer_check import (
    parse_layer_map,
    render_markdown,
    run_layer_check,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "layercheck_demo" / "pipeline.sql"
SQL = DEMO.read_text("utf-8")


def _check(sql: str = SQL, layers=None):
    return run_layer_check(sql, layers=layers)


# ── checker ──────────────────────────────────────────────────────────

def test_demo_violations():
    result = _check()
    codes = [f.code for f in result.findings]
    assert codes == ["LC001", "LC002", "LC003"]
    skip = result.findings[0]
    assert skip.detail["src"] == "ods.orders_raw"
    assert skip.detail["dst"] == "ads.board_kpi"
    assert skip.detail["skipped"] == 2 and skip.severity == "high"


def test_reverse_dependency_high():
    f = next(f for f in _check().findings if f.code == "LC002")
    assert f.detail["dst"] == "dwd.orders_enriched"
    assert f.severity == "high"


def test_ods_to_dws_is_mid():
    sql = "INSERT INTO dws.daily SELECT dt FROM ods.raw;"
    f = next(f for f in _check(sql).findings if f.code == "LC001")
    assert f.severity == "mid" and f.detail["skipped"] == 1


def test_clean_pipeline():
    sql = ("INSERT INTO dwd.o SELECT * FROM ods.raw;\n"
           "INSERT INTO dws.d SELECT * FROM dwd.o;\n"
           "INSERT INTO ads.k SELECT * FROM dws.d;")
    result = _check(sql)
    assert result.findings == []
    assert "符合分层拓扑" in render_markdown(result, lang="zh")


def test_dim_readable_everywhere():
    sql = ("INSERT INTO dws.d SELECT * FROM dim.users;\n"
           "INSERT INTO ads.k SELECT * FROM dws.d;")
    codes = {f.code for f in _check(sql).findings}
    assert "LC002" not in codes
    # dim (rank 1) -> ads (rank 3) still skips dws: flagged as LC001
    sql2 = "INSERT INTO ads.k SELECT * FROM dim.users;"
    assert any(f.code == "LC001" for f in _check(sql2).findings)


def test_unknown_layer_listed_and_tmp_ignored():
    sql = ("INSERT INTO mystery.t SELECT * FROM ods.raw;\n"
           "INSERT INTO tmp.x SELECT * FROM ads.k;")
    result = _check(sql)
    unk = next(f for f in result.findings if f.code == "LC004")
    assert unk.detail["tables"] == ["mystery.t"]
    # tmp edges are skipped entirely (no LC002 for tmp reading ads)
    assert not any(f.code == "LC002" for f in result.findings)


def test_custom_layer_map_replaces_builtin():
    layers = parse_layer_map('{"raw": 0, "core": 1, "mart": 2}')
    sql = "INSERT INTO mart.k SELECT * FROM raw.t;"
    result = _check(sql, layers=layers)
    assert any(f.code == "LC001" for f in result.findings)
    # the builtin prefixes are gone under a custom map
    sql2 = "INSERT INTO dws.d SELECT * FROM ods.raw;"
    result2 = _check(sql2, layers=layers)
    assert any(f.code == "LC004" for f in result2.findings)


def test_parse_layer_map_rejects_garbage():
    import pytest

    with pytest.raises(ValueError):
        parse_layer_map("  ")
    with pytest.raises(ValueError):
        parse_layer_map("not json")
    with pytest.raises(ValueError):
        parse_layer_map('{"ods": "zero"}')


def test_report_both_langs():
    result = _check()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "数仓分层体检" in zh and "跨层引用" in zh
    assert "Warehouse Layering Check" in en and "reverse dependency" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.layer_check import api as lc_api

    app = FastAPI()
    app.include_router(lc_api.router)
    return TestClient(app)


def test_api_check_inline():
    res = _client().post("/api/layercheck/check",
                         json={"sql_text": SQL, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["findings"]) == 3
    assert "Warehouse Layering Check" in body["report"]


def test_api_custom_layers():
    res = _client().post("/api/layercheck/check", json={
        "sql_text": "INSERT INTO mart.k SELECT * FROM raw.t;",
        "layers_text": '{"raw": 0, "core": 1, "mart": 2}'})
    assert res.status_code == 200
    assert any(f["code"] == "LC001"
               for f in res.json()["result"]["findings"])


def test_api_bad_input_400():
    assert _client().post("/api/layercheck/check",
                          json={"sql_text": "  "}).status_code == 400
    assert _client().post("/api/layercheck/check",
                          json={"sql_text": SQL,
                                "layers_text": "junk"}).status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("LAYERCHECK_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/layercheck/check",
                         json={"sql_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/layercheck/check",
                         json={"sql_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.layer_check import advisor_llm

    monkeypatch.setattr(advisor_llm, "layering_note",
                        lambda result, lang="zh": "LAYER-NOTE")
    res = _client().post("/api/layercheck/check",
                         json={"sql_text": SQL, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["layering_note"] == "LAYER-NOTE"


def test_api_health():
    body = _client().get("/api/layercheck/health").json()
    assert body == {"status": "ok", "agent": "layer_check"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_layercheck_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["layercheck", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数仓分层体检" in res.output and "LC002" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["layercheck", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "layercheck", "--text",
        "INSERT INTO dwd.o SELECT * FROM ods.raw;", "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "layer_check" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.layer_check.tools import layer_check

    out = layer_check(SQL, lang="en")
    assert "Warehouse Layering Check" in out and "LC001" in out
    assert "must not be empty" in layer_check("  ")
    assert "bad input" in layer_check(SQL, layers="junk")
