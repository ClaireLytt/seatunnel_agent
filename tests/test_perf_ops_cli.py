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


def test_sqlcost_what_if_partition():
    runner = CliRunner()
    args = ["--sql-file", str(EX / "sqlcost_demo" / "query.sql"),
            "-f", str(EX / "sqlcost_demo" / "stats.json")]
    # partitioning users by the equality-joined key cuts its scan
    res = runner.invoke(sqlcost, [*args, "--assume-partition",
                                  "ods.users:user_id:10", "-F", "json"])
    assert res.exit_code == 0
    whatif = json.loads(res.output)["what_if"]
    assert whatif["scan_saved_pct"] > 0
    # malformed spec and unknown partition count are usage errors
    assert runner.invoke(sqlcost, [*args, "--assume-partition", "nope"]
                         ).exit_code == 2
    assert runner.invoke(sqlcost, [*args, "--assume-partition",
                                   "ods.users:user_id"]).exit_code == 2


def test_slowquery_regression_gate():
    runner = CliRunner()
    args = ["-f", str(EX / "slowquery_demo" / "metrics.json"),
            "--baseline", str(EX / "slowquery_demo" / "baseline.jsonl")]
    # demo regression is 4.19x: a 3x limit trips, a 10x limit passes
    res = runner.invoke(slowquery, [*args, "--fail-over-regression", "3"])
    assert res.exit_code == 1 and "REGRESSION 4.19x" in res.output
    assert runner.invoke(slowquery, [*args, "--fail-over-regression", "10"]
                         ).exit_code == 0


def test_slowquery_batch_dir(tmp_path):
    """-d dir: every *.json diagnosed, ranked by regression, worst gates."""
    import shutil

    runs = tmp_path / "runs"
    runs.mkdir()
    src = EX / "slowquery_demo" / "metrics.json"
    shutil.copy(src, runs / "heavy.json")
    fast = json.loads(src.read_text("utf-8"))
    fast["name"], fast["duration_s"] = "fast_run", 400
    (runs / "fast.json").write_text(json.dumps(fast), encoding="utf-8")

    runner = CliRunner()
    args = ["-d", str(runs),
            "--baseline", str(EX / "slowquery_demo" / "baseline.jsonl")]
    res = runner.invoke(slowquery, [*args, "-F", "json"])
    assert res.exit_code == 0
    ranked = json.loads(res.output)["runs"]
    assert [r["regression"] >= ranked[-1]["regression"] for r in ranked]
    assert ranked[0]["duration_s"] == 1800  # the heavy run first
    # the worst run trips the gate; batch mode refuses --llm
    res = runner.invoke(slowquery, [*args, "--fail-over-regression", "3"])
    assert res.exit_code == 1 and "REGRESSION" in res.output
    assert runner.invoke(slowquery, [*args, "--llm"]).exit_code == 2


def test_sqlperf_plan_diff():
    runner = CliRunner()
    res = runner.invoke(sqlperf, [
        "-f", str(EX / "sqlperf_demo" / "plan_optimized.txt"),
        "--before", str(EX / "sqlperf_demo" / "plan.txt"),
        "-F", "json"])
    assert res.exit_code == 0
    diff = json.loads(res.output)["diff"]
    resolved = {f["code"] for f in diff["resolved"]}
    assert "PF002" in resolved and "PF005" in resolved
    assert diff["exchanges"] == {"before": 3, "after": 2}
    assert any(c["table"] == "ods.orders" for c in diff["scan_changes"])
    # identical plans -> everything remains, nothing resolved
    res = runner.invoke(sqlperf, [
        "-f", str(EX / "sqlperf_demo" / "plan.txt"),
        "--before", str(EX / "sqlperf_demo" / "plan.txt"), "-F", "json"])
    diff = json.loads(res.output)["diff"]
    assert not diff["resolved"] and not diff["introduced"]


def test_sqlperf_fail_on_new_gate():
    runner = CliRunner()
    good = str(EX / "sqlperf_demo" / "plan_optimized.txt")
    bad = str(EX / "sqlperf_demo" / "plan.txt")
    # optimized plan introduces nothing -> pass
    res = runner.invoke(sqlperf, ["-f", good, "--before", bad,
                                  "--fail-on-new"])
    assert res.exit_code == 0
    # reversed direction introduces findings -> gate trips
    res = runner.invoke(sqlperf, ["-f", bad, "--before", good,
                                  "--fail-on-new"])
    assert res.exit_code == 1 and "INTRODUCED" in res.output
    # without --before it is a usage error
    res = runner.invoke(sqlperf, ["-f", bad, "--fail-on-new"])
    assert res.exit_code == 2


def test_slowquery_promote_baseline(tmp_path):
    runner = CliRunner()
    base = tmp_path / "base.jsonl"
    base.write_text(
        '{"ts": "t1", "duration_s": 400, "scan_bytes": 1000}\n'
        '{"ts": "t2", "duration_s": 420, "scan_bytes": 1000}\n'
        '{"ts": "t3", "duration_s": 410, "scan_bytes": 1000}\n',
        encoding="utf-8")
    metrics = tmp_path / "m.json"
    metrics.write_text('{"name": "q1", "duration_s": 430, '
                       '"scan_bytes": 1100}', encoding="utf-8")
    res = runner.invoke(slowquery, [
        "-f", str(metrics), "--baseline", str(base), "--promote-baseline"])
    assert res.exit_code == 0
    lines = base.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4 and json.loads(lines[-1])["duration_s"] == 430
    # a regressed run must not be promoted
    metrics.write_text('{"name": "q1", "duration_s": 5000}',
                       encoding="utf-8")
    res = runner.invoke(slowquery, [
        "-f", str(metrics), "--baseline", str(base), "--promote-baseline"])
    assert res.exit_code == 0
    assert len(base.read_text(encoding="utf-8").strip().splitlines()) == 4
    # without --baseline it is a usage error; in --dir mode too
    res = runner.invoke(slowquery, ["-f", str(metrics),
                                    "--promote-baseline"])
    assert res.exit_code == 2
    res = runner.invoke(slowquery, ["-d", str(tmp_path), "--baseline",
                                    str(base), "--promote-baseline"])
    assert res.exit_code == 2


def test_index_adv_layout_audit():
    runner = CliRunner()
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--ddl", str(EX / "indexadvisor_demo" / "ddl_legacy.sql"),
        "-F", "json"])
    assert res.exit_code == 0
    findings = json.loads(res.output)["audit"]
    codes = {(f["code"], f["table"]) for f in findings}
    assert ("IA002", "ods.orders") in codes  # status -> dt
    assert ("IA004", "ods.users") in codes   # updated_at never joined
    assert ("IA003", "ods.users") in codes
    # clean DDL (no declared layout): no IA001/IA004, only gaps
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--ddl", str(EX / "indexadvisor_demo" / "ddl.sql"), "--lang", "en"])
    assert res.exit_code == 0 and "Layout audit" in res.output
    assert "IA001" not in res.output and "IA004" not in res.output


def test_index_adv_fail_on_audit_gate():
    runner = CliRunner()
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--ddl", str(EX / "indexadvisor_demo" / "ddl_legacy.sql"),
        "--fail-on-audit"])
    assert res.exit_code == 1 and "AUDIT IA002" in res.output
    # a layout matching the workload passes the gate
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--ddl", str(EX / "indexadvisor_demo" / "ddl_tuned.sql"),
        "--fail-on-audit"])
    assert res.exit_code == 0
    # without --ddl it is a usage error
    res = runner.invoke(index_adv, ["-d", str(EX / "indexadvisor_demo"),
                                    "--fail-on-audit"])
    assert res.exit_code == 2


def test_sqlcost_fail_if_worse_gate():
    runner = CliRunner()
    stats = str(EX / "sqlcost_demo" / "stats.json")
    full = str(EX / "sqlcost_demo" / "query_full_scan.sql")
    pruned = str(EX / "sqlcost_demo" / "query_rewritten.sql")
    # rewrite saves on every axis -> pass
    res = runner.invoke(sqlcost, ["--sql-file", full, "-f", stats,
                                  "--compare-sql-file", pruned,
                                  "--fail-if-worse"])
    assert res.exit_code == 0
    # reversed direction is worse -> gate trips and names the axes
    res = runner.invoke(sqlcost, ["--sql-file", pruned, "-f", stats,
                                  "--compare-sql-file", full,
                                  "--fail-if-worse"])
    assert res.exit_code == 1 and "WORSE scan" in res.output
    # without --compare-sql-file it is a usage error
    res = runner.invoke(sqlcost, ["--sql-file", full, "-f", stats,
                                  "--fail-if-worse"])
    assert res.exit_code == 2


def test_slowquery_trend_gate(tmp_path):
    runner = CliRunner()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        '{"ts": "t1", "duration_s": 400}\n'
        '{"ts": "t2", "duration_s": 440}\n'
        '{"ts": "t3", "duration_s": 480}\n'
        '{"ts": "t4", "duration_s": 520}\n', encoding="utf-8")
    metrics = tmp_path / "m.json"
    metrics.write_text('{"name": "q1", "duration_s": 560}',
                       encoding="utf-8")
    res = runner.invoke(slowquery, [
        "-f", str(metrics), "--history", str(ledger), "--trend", "5",
        "--fail-on-trend"])
    assert res.exit_code == 1 and "TREND" in res.output
    # a run that breaks the rise passes the gate
    metrics.write_text('{"name": "q1", "duration_s": 480}',
                       encoding="utf-8")
    res = runner.invoke(slowquery, [
        "-f", str(metrics), "--history", str(ledger), "--trend", "5",
        "--fail-on-trend", "-F", "json"])
    assert res.exit_code == 0
    payload, _ = json.JSONDecoder().raw_decode(res.output)
    assert "trend" not in payload
    # usage errors: trend without history; fail-on-trend without --trend
    res = runner.invoke(slowquery, ["-f", str(metrics), "--trend", "5"])
    assert res.exit_code == 2
    res = runner.invoke(slowquery, ["-f", str(metrics), "--history",
                                    str(ledger), "--fail-on-trend"])
    assert res.exit_code == 2


def test_dagconflict_place():
    runner = CliRunner()
    demo = EX / "dagconflict_demo" / "scenario.json"
    res = runner.invoke(dagconflict, ["-f", str(demo), "--place",
                                      "etl_users", "-F", "json"])
    assert res.exit_code == 0
    placement = json.loads(res.output)["placement"]
    best, declared = placement["best"], placement["declared"]
    # the demo scenario conflicts at the declared offset; the best
    # candidate removes every window and write conflict
    assert declared["windows"] + declared["write_conflicts"] > 0
    assert best["windows"] == 0 and best["write_conflicts"] == 0
    assert best["offset"] != declared["offset"]
    # unknown dag is a usage error
    res = runner.invoke(dagconflict, ["-f", str(demo), "--place", "nope"])
    assert res.exit_code == 2
    # markdown shows the candidate table
    res = runner.invoke(dagconflict, ["-f", str(demo), "--place",
                                      "etl_users", "--lang", "en"])
    assert res.exit_code == 0 and "Admission check" in res.output


def test_sqlcost_compare_rewrite():
    runner = CliRunner()
    res = runner.invoke(sqlcost, [
        "--sql-file", str(EX / "sqlcost_demo" / "query_full_scan.sql"),
        "-f", str(EX / "sqlcost_demo" / "stats.json"),
        "--compare-sql-file",
        str(EX / "sqlcost_demo" / "query_rewritten.sql"),
        "-F", "json"])
    assert res.exit_code == 0
    cmp = json.loads(res.output)["compare"]
    assert cmp["saved_pct"]["scan"] > 90  # pruning 365 partitions
    assert cmp["rewrite"]["scan_bytes"] < cmp["base"]["scan_bytes"]
    # markdown path renders the comparison table
    res = runner.invoke(sqlcost, [
        "--sql-file", str(EX / "sqlcost_demo" / "query_full_scan.sql"),
        "-f", str(EX / "sqlcost_demo" / "stats.json"),
        "--compare-sql-file",
        str(EX / "sqlcost_demo" / "query_rewritten.sql"), "--lang", "en"])
    assert res.exit_code == 0 and "Rewrite comparison" in res.output
