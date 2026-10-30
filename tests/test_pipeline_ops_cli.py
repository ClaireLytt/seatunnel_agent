"""CLI tests for the pipeline-ops suite commands (click CliRunner)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli_cmds.pipeline_ops import (
    backfill_sql,
    dagopt,
    pipe_migrate,
    rerun,
    sync_strategy,
)

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"


def test_dagopt_cli_markdown_and_json():
    runner = CliRunner()
    res = runner.invoke(dagopt, ["-f", str(EX / "dagopt_demo" / "dag.json"),
                                 "--lang", "en"])
    assert res.exit_code == 0
    assert "DAG Dependency Optimization" in res.output
    res = runner.invoke(dagopt, ["-f", str(EX / "dagopt_demo" / "dag.json"),
                                 "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["tasks"] == 7


def test_rerun_cli_failed_and_statuses():
    runner = CliRunner()
    dag = str(EX / "rerun_demo" / "dag.json")
    res = runner.invoke(rerun, ["-f", dag, "--failed", "clean_orders",
                                "--lang", "en"])
    assert res.exit_code == 0
    assert "blast radius" in res.output
    res = runner.invoke(rerun, ["-f", dag, "--statuses",
                                '{"clean_orders":"failed"}', "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["total"] == 8
    res = runner.invoke(rerun, ["-f", dag])
    assert res.exit_code != 0  # neither --failed nor --statuses


def test_backfill_sql_cli_spec_and_plan(tmp_path):
    runner = CliRunner()
    out = tmp_path / "report.md"
    res = runner.invoke(backfill_sql, [
        "-f", str(EX / "backfillsql_demo" / "spec.json"),
        "--lang", "en", "-o", str(out)])
    assert res.exit_code == 0
    assert "INSERT OVERWRITE TABLE dws.sales" in out.read_text("utf-8")
    plan = ('{"tables":[{"table":"dws.sales",'
            '"missing":["2024-05-05"],"cascade":[]}]}')
    res = runner.invoke(backfill_sql, ["--plan", plan, "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["specs"][0]["dates"] == ["2024-05-05"]


def test_sync_strategy_cli():
    runner = CliRunner()
    res = runner.invoke(sync_strategy, [
        "-f", str(EX / "syncstrategy_demo" / "tables.json"), "--lang", "en"])
    assert res.exit_code == 0
    assert "Sync Strategy Recommendation" in res.output


def test_pipe_migrate_cli_dir_and_file():
    runner = CliRunner()
    res = runner.invoke(pipe_migrate, [
        "-d", str(EX / "pipemigrate_demo"), "--lang", "en"])
    assert res.exit_code == 0
    assert "Pipeline Migration Assessment" in res.output
    res = runner.invoke(pipe_migrate, [
        "-f", str(EX / "pipemigrate_demo" / "build_sales.hql"), "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["jobs"][0]["job"] == "build_sales.hql"
    res = runner.invoke(pipe_migrate, [])
    assert res.exit_code != 0  # neither --dir nor --file
