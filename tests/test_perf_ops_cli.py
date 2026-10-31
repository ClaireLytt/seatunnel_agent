"""CLI tests for the SQL performance suite commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli_cmds.perf_ops import (
    dagconflict,
    index_adv,
    slowquery,
    sqlcost,
    sqlperf,
)

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"


def test_sqlperf_cli():
    runner = CliRunner()
    res = runner.invoke(sqlperf, ["-f", str(EX / "sqlperf_demo" / "plan.txt"),
                                  "--lang", "en"])
    assert res.exit_code == 0 and "PF002" in res.output
    res = runner.invoke(sqlperf, ["-f", str(EX / "sqlperf_demo" / "plan.txt"),
                                  "-F", "json"])
    assert json.loads(res.output)["exchanges"] == 3
    # --llm without --sql-file is a usage error, not a half-run
    res = runner.invoke(sqlperf, ["-f", str(EX / "sqlperf_demo" / "plan.txt"),
                                  "--llm"])
    assert res.exit_code == 2


def test_sqlperf_llm_rewrite_wiring(monkeypatch, tmp_path):
    from seatunnel_agent.agents.data.sql_perf import advisor_llm

    monkeypatch.setattr(advisor_llm, "rewrite_sql",
                        lambda report, sql, lang="zh": "REWRITTEN " + sql[:10])
    sql = tmp_path / "q.sql"
    sql.write_text("SELECT 1 FROM t", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(sqlperf, ["-f", str(EX / "sqlperf_demo" / "plan.txt"),
                                  "--llm", "--sql-file", str(sql),
                                  "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["rewrite"].startswith("REWRITTEN")


def test_index_adv_cli():
    runner = CliRunner()
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--ddl", str(EX / "indexadvisor_demo" / "ddl.sql"), "--lang", "en"])
    assert res.exit_code == 0 and "PARTITIONED BY (dt)" in res.output


def test_sqlcost_cli_and_budget_gate():
    runner = CliRunner()
    args = ["--sql-file", str(EX / "sqlcost_demo" / "query.sql"),
            "-f", str(EX / "sqlcost_demo" / "stats.json")]
    res = runner.invoke(sqlcost, [*args, "--lang", "en"])
    assert res.exit_code == 0 and "SQL Cost Card" in res.output
    # demo scan ≈ 0.14 GB: a 10 GB budget passes, a 0.01 GB budget fails
    assert runner.invoke(sqlcost, [*args, "--fail-over-scan-gb", "10"]
                         ).exit_code == 0
    res = runner.invoke(sqlcost, [*args, "--fail-over-scan-gb", "0.01"])
    assert res.exit_code == 1 and "BUDGET scan" in res.output


def test_slowquery_cli_and_ledger(tmp_path):
    runner = CliRunner()
    hist = tmp_path / "slow_ledger.jsonl"
    args = ["-f", str(EX / "slowquery_demo" / "metrics.json"),
            "--baseline", str(EX / "slowquery_demo" / "baseline.jsonl"),
            "--history", str(hist)]
    res = runner.invoke(slowquery, args)
    assert res.exit_code == 0 and "首次记录" in res.output
    entry = json.loads(hist.read_text("utf-8").splitlines()[0])
    assert entry["regression"] == 4.19 and entry["top_share"] > 0.6


def test_dagconflict_cli():
    runner = CliRunner()
    res = runner.invoke(dagconflict, [
        "-f", str(EX / "dagconflict_demo" / "scenario.json"), "--lang", "en"])
    assert res.exit_code == 0 and "Stagger suggestion" in res.output


def test_slowquery_llm_note_wiring(monkeypatch):
    from seatunnel_agent.agents.data.slow_query import advisor_llm

    monkeypatch.setattr(advisor_llm, "incident_note",
                        lambda diag, lang="zh": "NOTE-CLI")
    runner = CliRunner()
    res = runner.invoke(slowquery, [
        "-f", str(EX / "slowquery_demo" / "metrics.json"),
        "--llm", "-F", "json"])
    assert res.exit_code == 0
    assert json.loads(res.output)["incident_note"] == "NOTE-CLI"


def test_sqlperf_severity_gate():
    runner = CliRunner()
    args = ["-f", str(EX / "sqlperf_demo" / "plan.txt")]
    # the demo plan has high findings (PF002) -> high gate trips
    res = runner.invoke(sqlperf, [*args, "--fail-on-severity", "high"])
    assert res.exit_code == 1 and "FINDING PF002" in res.output
    # a clean plan passes
    res = runner.invoke(sqlperf, [
        "--text", "FileScan parquet db.t[id] PartitionFilters: [dt=1], "
                  "PushedFilters: [IsNotNull(id)]",
        "--fail-on-severity", "high"])
    assert res.exit_code == 0


def test_dagconflict_gate_and_ledger(tmp_path):
    runner = CliRunner()
    hist = tmp_path / "capacity.jsonl"
    args = ["-f", str(EX / "dagconflict_demo" / "scenario.json"),
            "--history", str(hist)]
    # the demo scenario has conflicts -> gate trips, ledger still written
    res = runner.invoke(dagconflict, [*args, "--fail-on-conflict"])
    assert res.exit_code == 1 and "CONFLICT windows=" in res.output
    entry = json.loads(hist.read_text("utf-8").splitlines()[0])
    assert entry["peak_slots"] > 0 and entry["write_conflicts"] >= 0
