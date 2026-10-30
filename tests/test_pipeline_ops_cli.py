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


def test_dagopt_history_tracking(tmp_path):
    runner = CliRunner()
    hist = tmp_path / "runs" / "dag_history.jsonl"
    dag = str(EX / "dagopt_demo" / "dag.json")
    res = runner.invoke(dagopt, ["-f", dag, "--history", str(hist)])
    assert res.exit_code == 0 and "首次记录" in res.output
    # slower variant → drift line flags the critical-path creep
    slower = json.loads((EX / "dagopt_demo" / "dag.json")
                        .read_text("utf-8"))
    slower["tasks"][4]["duration"] = 20  # join_wide 12 → 20
    res = runner.invoke(dagopt, ["--text", json.dumps(slower),
                                 "--history", str(hist)])
    assert res.exit_code == 0
    assert "critical 35 → 43" in res.output
    # two jsonl records on disk, parseable
    lines = hist.read_text("utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["critical"] == 43.0
    # identical rerun reports steady state
    res = runner.invoke(dagopt, ["--text", json.dumps(slower),
                                 "--history", str(hist)])
    assert "持平" in res.output


def test_dagopt_regression_gate(tmp_path):
    runner = CliRunner()
    base = tmp_path / "base.json"
    base.write_text(
        '{"tasks":[{"name":"a","duration":5},'
        '{"name":"b","deps":["a"],"duration":5}]}', encoding="utf-8")
    slower = ('{"tasks":[{"name":"a","duration":5},'
              '{"name":"b","deps":["a"],"duration":9}]}')
    # regression beyond tolerance → exit 1 with the reason
    res = runner.invoke(dagopt, ["--text", slower, "--base", str(base),
                                 "--fail-on-regression"])
    assert res.exit_code == 1
    assert "REGRESSION" in res.output and "+4" in res.output
    # within tolerance → green
    res = runner.invoke(dagopt, ["--text", slower, "--base", str(base),
                                 "--fail-on-regression", "--tolerance", "5"])
    assert res.exit_code == 0
    # introduced redundancy fails even with a duration tolerance
    redundant = ('{"tasks":[{"name":"a","duration":5},'
                 '{"name":"b","deps":["a"],"duration":5},'
                 '{"name":"c","deps":["b","a"],"duration":1}]}')
    res = runner.invoke(dagopt, ["--text", redundant, "--base", str(base),
                                 "--fail-on-regression", "--tolerance", "99"])
    assert res.exit_code == 1 and "a->c" in res.output
    # gate without a base is a usage error
    res = runner.invoke(dagopt, ["--text", slower, "--fail-on-regression"])
    assert res.exit_code == 2


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


def test_sync_strategy_risk_gate():
    runner = CliRunner()
    inv = str(EX / "syncstrategy_demo" / "tables.json")
    # demo has no table with the latency risk → green
    res = runner.invoke(sync_strategy, [
        "-f", inv, "--fail-on-risk", "latency_without_cdc"])
    assert res.exit_code == 0
    # a minutes-latency table without binlog trips the gate
    bad = ('[{"table":"ods.t","rows":5000000,"has_update_ts":true,'
           '"has_pk":true,"latency":"minutes"}]')
    res = runner.invoke(sync_strategy, [
        "--text", bad, "--fail-on-risk", "latency_without_cdc"])
    assert res.exit_code == 1
    assert "RISK" in res.output and "ods.t" in res.output
    # typo in the code is a usage error naming the known set
    res = runner.invoke(sync_strategy, [
        "--text", bad, "--fail-on-risk", "latenzy"])
    assert res.exit_code == 2 and "latency_without_cdc" in res.output


def test_sync_strategy_emit_configs(tmp_path):
    runner = CliRunner()
    out = tmp_path / "confs"
    res = runner.invoke(sync_strategy, [
        "-f", str(EX / "syncstrategy_demo" / "tables.json"),
        "--emit-configs", str(out)])
    assert res.exit_code == 0
    files = sorted(p.name for p in out.glob("*.conf"))
    assert "ods_orders.conf" in files and len(files) == 5
    conf = (out / "ods_orders.conf").read_text("utf-8")
    assert "MySQL-CDC" in conf  # cdc recommendation carried into the file


def test_pipe_migrate_emit_stubs(tmp_path):
    runner = CliRunner()
    out = tmp_path / "stubs"
    res = runner.invoke(pipe_migrate, [
        "-d", str(EX / "pipemigrate_demo"), "--emit-stubs", str(out)])
    assert res.exit_code == 0
    files = sorted(p.name for p in out.glob("*.conf"))
    # only the SeaTunnel-target jobs with stubs land on disk
    assert files == ["datax_items_json.conf", "sync_orders_sh.conf"]
    assert "HdfsFile" in (out / "sync_orders_sh.conf").read_text("utf-8")


def test_backfill_sql_runner_in_cli(tmp_path):
    import json as _json

    runner = CliRunner()
    spec = _json.loads((EX / "backfillsql_demo" / "spec.json")
                       .read_text("utf-8"))
    spec["runner"] = "beeline"
    res = runner.invoke(backfill_sql, ["--text", _json.dumps(spec),
                                       "-F", "json"])
    assert res.exit_code == 0
    assert 'beeline -u "$JDBC_URL"' in _json.loads(res.output)["runner_script"]


def test_pipe_migrate_burn_down_history(tmp_path):
    import shutil

    runner = CliRunner()
    hist = tmp_path / "burndown.jsonl"
    legacy = tmp_path / "legacy"
    shutil.copytree(EX / "pipemigrate_demo", legacy)
    res = runner.invoke(pipe_migrate, ["-d", str(legacy),
                                       "--history", str(hist)])
    assert res.exit_code == 0 and "首次记录" in res.output
    # a job got migrated away → the burn-down shows jobs shrinking
    (legacy / "sync_orders.sh").unlink()
    res = runner.invoke(pipe_migrate, ["-d", str(legacy),
                                       "--history", str(hist)])
    assert res.exit_code == 0
    assert "jobs 6 → 5" in res.output
    assert "to_seatunnel 2 → 1" in res.output
    lines = hist.read_text("utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["jobs"] == 5


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
