"""Tests for the dag_gen agent (generator / report / CLI / tool / API)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.dag_gen import generate_dag, render_markdown

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "daggen_demo" / "pipeline.sql"


def _demo_draft(**kw):
    return generate_dag(DEMO.read_text(encoding="utf-8"),
                        dag_id="demo_daily", **kw)


# --------------------------------------------------------------- generator

def test_demo_tasks_edges_externals():
    draft = _demo_draft()
    assert len(draft.tasks) == 3 and draft.edges == 2
    by = {t.task_id: t for t in draft.tasks}
    assert set(by["ads_final_report"].upstream) == {"ads_order_counts",
                                                    "dws_orders_daily"}
    assert by["dws_orders_daily"].external == ["dim.users", "dwd.orders"]
    assert draft.externals == ["dim.users", "dwd.orders"]


def test_python_parses_and_wires_edges():
    draft = _demo_draft()
    ast.parse(draft.python_text)             # importable skeleton
    assert 'dag_id="demo_daily"' in draft.python_text
    assert "dws_orders_daily >> ads_final_report" in draft.python_text
    assert "<RUN ads.final_report>" in draft.python_text
    assert "add sensors" in draft.python_text


def test_schedule_and_dialect_passthrough():
    draft = generate_dag("INSERT INTO a.t SELECT x FROM s",
                         schedule="30 6 * * *")
    assert 'schedule="30 6 * * *"' in draft.python_text


def test_task_id_sanitized_and_deduped():
    sql = ("INSERT INTO db.`my-table` SELECT x FROM s;"
           "INSERT INTO db.my_table SELECT x FROM s")
    draft = generate_dag(sql)
    ids = {t.task_id for t in draft.tasks}
    assert len(ids) == 2 and "db_my_table" in ids


def test_bad_inputs():
    with pytest.raises(ValueError, match="dag_id"):
        generate_dag("INSERT INTO t SELECT 1 FROM s", dag_id="bad id!")
    with pytest.raises(ValueError, match="no write statements"):
        generate_dag("SELECT 1")
    with pytest.raises(ValueError, match="empty"):
        generate_dag("   ")


def test_dolphinscheduler_engine_round_trips():
    import json

    draft = _demo_draft(engine="dolphinscheduler")
    doc = json.loads(draft.python_text)
    assert doc["name"] == "demo_daily"
    assert doc["schedule"]["crontab"] == "0 2 * * *"
    names = {t["name"]: t for t in doc["taskDefinitionList"]}
    assert set(names) == {"dws_orders_daily", "ads_order_counts",
                          "ads_final_report"}
    assert names["dws_orders_daily"]["taskParams"]["rawScript"] == (
        "echo <RUN dws.orders_daily>")
    assert "dim.users" in names["dws_orders_daily"]["description"]
    codes = {t["name"]: t["code"] for t in doc["taskDefinitionList"]}
    rel = {(r["preTaskCode"], r["postTaskCode"])
           for r in doc["taskRelationList"]}
    assert (codes["dws_orders_daily"], codes["ads_final_report"]) in rel
    assert (0, codes["dws_orders_daily"]) in rel      # root relation


def test_azkaban_engine_round_trips():
    import yaml

    draft = _demo_draft(engine="azkaban")
    doc = yaml.safe_load(draft.python_text)
    assert doc["config"]["schedule"] == "0 2 * * *"
    nodes = {n["name"]: n for n in doc["nodes"]}
    assert nodes["ads_final_report"]["type"] == "command"
    assert set(nodes["ads_final_report"]["dependsOn"]) == {
        "ads_order_counts", "dws_orders_daily"}
    assert nodes["dws_orders_daily"]["config"]["command"] == (
        "echo <RUN dws.orders_daily>")
    assert "dependsOn" not in nodes["dws_orders_daily"]
    with pytest.raises(ValueError, match="engine"):
        _demo_draft(engine="oozie")


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = _demo_draft()
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "DAG 草稿" in zh and "```python" in zh
    assert "Airflow DAG Draft" in en and "ads_final_report" in en
    ds = render_markdown(_demo_draft(engine="dolphinscheduler"),
                         lang="en")
    assert "DolphinScheduler Definition Draft" in ds and "```json" in ds
    az = render_markdown(_demo_draft(engine="azkaban"), lang="zh")
    assert "Azkaban Flow 草稿" in az and "```yaml" in az


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_py_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["daggen", "-f", str(DEMO), "--dag-id", "demo_daily"]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "DAG 草稿" in res.output
    out = tmp_path / "dag.py"
    res = runner.invoke(cli, args + ["--py-out", str(out),
                                     "--format", "json"])
    assert res.exit_code == 0 and '"tasks_total": 3' in res.output
    ast.parse(out.read_text(encoding="utf-8"))
    flow = tmp_path / "demo.flow"
    res = runner.invoke(cli, args + ["--engine", "azkaban",
                                     "--py-out", str(flow)])
    assert res.exit_code == 0, res.output
    assert "Azkaban Flow 草稿" in res.output
    assert "dependsOn:" in flow.read_text(encoding="utf-8")


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["daggen", "--text", "SELECT 1"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.dag_gen.tools import dag_gen

    out = dag_gen(DEMO.read_text(encoding="utf-8"), dag_id="demo_daily",
                  lang="en")
    assert "Airflow DAG Draft" in out and "BashOperator" in out
    assert "must not be empty" in dag_gen("  ")
    assert "bad input" in dag_gen("SELECT 1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.dag_gen.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_and_health():
    client = _client()
    assert client.get("/api/daggen/health").status_code == 200
    resp = client.post("/api/daggen/generate", json={
        "sql_text": DEMO.read_text(encoding="utf-8"),
        "dag_id": "demo_daily", "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["tasks_total"] == 3
    assert "Airflow DAG Draft" in body["report"]
    resp = client.post("/api/daggen/generate", json={
        "sql_text": DEMO.read_text(encoding="utf-8"),
        "engine": "dolphinscheduler", "lang": "en", "report": True})
    assert resp.status_code == 200
    assert "DolphinScheduler Definition Draft" in resp.json()["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/daggen/generate",
                       json={"sql_text": "SELECT 1"})
    assert resp.status_code == 400
