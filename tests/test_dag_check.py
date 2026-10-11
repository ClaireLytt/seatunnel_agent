# -*- coding: utf-8 -*-
"""Tests for the scheduling DAG health checker (dag_check).

Deterministic only — no scheduler, no database, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.dag_check import (
    check_graph,
    check_sql_dir,
    render_markdown,
    report_to_dict,
)
from seatunnel_agent.dag_check.checker import _layer_of
from seatunnel_agent.data_lineage.graph import LineageGraph

runner = CliRunner()

DEMO = Path(__file__).resolve().parents[1] / "examples" / "dagcheck_demo"


def _graph(edges):
    g = LineageGraph()
    for src, dst in edges:
        g.add_edge(src, dst, source="sql")
    return g


def _finding(report, kind):
    return next((f for f in report.findings if f.kind == kind), None)


# ─────────────────────────── layer detection ───────────────────────────

@pytest.mark.parametrize("name,layer", [
    ("dwd.orders", "dwd"),
    ("warehouse.dws_gmv", "dws"),
    ("ads.report", "ads"),
    ("ods.raw", "ods"),
    ("foo.bar", ""),
])
def test_layer_of(name, layer):
    assert _layer_of(name) == layer


# ─────────────────────────── checks ───────────────────────────

def test_cycle_detected():
    report = check_graph(_graph([("tmp.a", "tmp.b"), ("tmp.b", "tmp.a")]))
    f = _finding(report, "cycle")
    assert f is not None and f.severity == "error"
    assert set(report.unschedulable) == {"tmp.a", "tmp.b"}


def test_dangling_mid_layer():
    report = check_graph(_graph([("dwd.missing", "ads.report")]))
    f = _finding(report, "dangling_mid")
    assert f is not None and f.tables == ["dwd.missing"]


def test_ods_root_is_not_dangling():
    report = check_graph(_graph([("ods.raw", "dwd.orders"),
                                 ("dwd.orders", "ads.report")]))
    assert _finding(report, "dangling_mid") is None


def test_unconsumed_mid_layer():
    report = check_graph(_graph([("ods.raw", "dws.dead")]))
    f = _finding(report, "unconsumed_mid")
    assert f is not None and f.tables == ["dws.dead"]


def test_ads_leaf_is_not_unconsumed():
    report = check_graph(_graph([("dws.gmv", "ads.report")]))
    f = _finding(report, "unconsumed_mid")
    assert f is None or "ads.report" not in f.tables


def test_isolated_tables():
    g = _graph([("ods.a", "dwd.b")])
    g.add_node("tmp.lonely")
    report = check_graph(g)
    f = _finding(report, "isolated")
    assert f is not None and f.tables == ["tmp.lonely"]
    assert f.severity == "info"


# ─────────────────────────── batches & critical path ───────────────────────────

def test_topological_batches():
    report = check_graph(_graph([
        ("ods.a", "dwd.b"), ("ods.a2", "dwd.b"), ("dwd.b", "ads.c")]))
    assert report.batches == [["ods.a", "ods.a2"], ["dwd.b"], ["ads.c"]]
    assert not report.unschedulable


def test_cycle_nodes_excluded_from_batches():
    report = check_graph(_graph([
        ("ods.a", "dwd.b"), ("tmp.x", "tmp.y"), ("tmp.y", "tmp.x")]))
    batched = {t for batch in report.batches for t in batch}
    assert batched == {"ods.a", "dwd.b"}
    assert set(report.unschedulable) == {"tmp.x", "tmp.y"}


def test_critical_path_is_longest_chain():
    report = check_graph(_graph([
        ("ods.a", "dwd.b"), ("dwd.b", "dws.c"), ("dws.c", "ads.d"),
        ("ods.a", "ads.short")]))
    assert report.critical_path == ["ods.a", "dwd.b", "dws.c", "ads.d"]


# ─────────────────────────── demo dir ───────────────────────────

def test_demo_dir():
    report = check_sql_dir(DEMO)
    c = report.counts()
    assert c["error"] == 1          # the tmp.a ↔ tmp.b cycle
    assert c["warn"] == 2           # dangling dwd.missing_src + dead dws.dead_metric
    assert report.critical_path == [
        "ods.orders", "dwd.orders", "dws.gmv", "ads.gmv_report"]


def test_empty_dir(tmp_path):
    report = check_sql_dir(tmp_path)
    assert report.tables == 0
    assert report.warnings


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    report = check_sql_dir(DEMO)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "调度 DAG 体检" in zh and "关键路径" in zh
    assert "DAG Health Check" in en and "Critical path" in en
    # the cycle chain renders closed exactly once
    assert "tmp.a → tmp.a" not in zh.replace("tmp.b → tmp.a", "")


def test_report_to_dict_is_json_serializable():
    data = report_to_dict(check_sql_dir(DEMO), "en")
    assert data["counts"]["error"] == 1
    json.dumps(data)


# ─────────────────────────── CLI ───────────────────────────

def test_cli_dagcheck():
    r = runner.invoke(cli, ["dagcheck", "--sql-dir", str(DEMO)])
    assert r.exit_code == 0, r.output
    assert "调度 DAG 体检" in r.output


def test_cli_dagcheck_fail_on(tmp_path):
    out = tmp_path / "dag.json"
    r = runner.invoke(cli, ["dagcheck", "--sql-dir", str(DEMO),
                            "-F", "json", "--fail-on", "error",
                            "-o", str(out)])
    assert r.exit_code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["error"] == 1


def test_cli_dagcheck_clean_passes(tmp_path):
    (tmp_path / "ok.sql").write_text(
        "INSERT OVERWRITE TABLE ads.r SELECT a FROM ods.s;",
        encoding="utf-8")
    r = runner.invoke(cli, ["dagcheck", "--sql-dir", str(tmp_path),
                            "--fail-on", "warn"])
    assert r.exit_code == 0, r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.dag_check.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_check(api_client):
    r = api_client.post("/api/dagcheck/check", json={
        "sql_dir": str(DEMO), "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["error"] == 1
    assert "DAG Health Check" in data["report"]


def test_api_check_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("DAGCHECK_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/dagcheck/check", json={"sql_dir": str(DEMO)})
    assert r.status_code == 403


def test_api_check_requires_dir(api_client):
    r = api_client.post("/api/dagcheck/check", json={"sql_dir": "no_such"})
    assert r.status_code == 400
    assert api_client.get("/api/dagcheck/health").json()["status"] == "ok"
