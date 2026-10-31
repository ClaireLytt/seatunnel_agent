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


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = _demo_draft()
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "DAG 草稿" in zh and "```python" in zh
    assert "Airflow DAG Draft" in en and "ads_final_report" in en


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


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/daggen/generate",
                       json={"sql_text": "SELECT 1"})
    assert resp.status_code == 400
