"""CLI tests for the SQL performance suite commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from seatunnel_agent.cli_cmds.perf_ops import (
    dagconflict,
    index_adv,
    perf_report,
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


def test_sqlperf_stats_template(tmp_path):
    runner = CliRunner()
    out = tmp_path / "stats.json"
    res = runner.invoke(sqlperf, ["-f", str(EX / "sqlperf_demo" / "plan.txt"),
                                  "--stats-template", str(out)])
    assert res.exit_code == 0
    tables = json.loads(out.read_text(encoding="utf-8"))["tables"]
    assert {t["table"] for t in tables} == {"ods.orders", "ods.users"}
    assert all(t["rows"] == 0 and t["columns"] > 0 for t in tables)
    # the filled-in skeleton is sqlcost-parseable as-is
    from seatunnel_agent.agents.data.sql_cost import parse_stats
    for t in tables:
        t.update(rows=1000, bytes=1 << 20, partitions=10)
    stats = parse_stats(json.dumps({"tables": tables}))
    assert "ods.orders" in stats


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


def test_index_adv_partition_roi():
    runner = CliRunner()
    stats = str(EX / "indexadvisor_demo" / "stats.json")
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"), "--stats", stats, "-F", "json"])
    assert res.exit_code == 0
    roi = json.loads(res.output)["roi"]
    rows = {r["table"]: r for r in roi["rows"]}
    # ods.orders: dt recommended, 365 declared partitions -> big saving
    assert rows["ods.orders"]["partition_col"] == "dt"
    assert rows["ods.orders"]["saved_bytes"] > 0
    assert rows["ods.orders"]["statements_estimated"] > 0
    # an already-as-recommended inventory prices nothing for that table
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"),
        "--stats", str(EX / "sqlcost_demo" / "stats.json"), "-F", "json"])
    tables = {r["table"] for r in json.loads(res.output)["roi"]["rows"]}
    assert "ods.orders" not in tables
    res = runner.invoke(index_adv, [
        "-d", str(EX / "indexadvisor_demo"), "--stats", stats,
        "--lang", "en"])
    assert res.exit_code == 0 and "Partition ROI" in res.output
    # bucket counts sized by table bytes: 100GB orders -> 512-capped
    # power of two, tiny dim.regions -> the 4 floor
    assert "CLUSTERED BY (user_id) INTO 512 BUCKETS" in res.output
    assert "INTO 4 BUCKETS" in res.output
    # without stats the conventional 32 is kept
    res = runner.invoke(index_adv, ["-d", str(EX / "indexadvisor_demo")])
    assert "INTO 32 BUCKETS" in res.output


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


def test_perf_report_one_shot(tmp_path):
    runner = CliRunner()
    root = tmp_path / "inputs"
    (root / "queries").mkdir(parents=True)
    (root / "workload").mkdir()
    # plan + before, metrics + baseline, queries + stats, scenario, workload
    (root / "plan.txt").write_text(
        (EX / "sqlperf_demo" / "plan.txt").read_text("utf-8"), "utf-8")
    (root / "plan_before.txt").write_text(
        (EX / "sqlperf_demo" / "plan.txt").read_text("utf-8"), "utf-8")
    (root / "metrics.json").write_text(
        (EX / "slowquery_demo" / "metrics.json").read_text("utf-8"), "utf-8")
    (root / "baseline.jsonl").write_text(
        (EX / "slowquery_demo" / "baseline.jsonl").read_text("utf-8"),
        "utf-8")
    (root / "queries" / "q.sql").write_text(
        (EX / "sqlcost_demo" / "query.sql").read_text("utf-8"), "utf-8")
    (root / "stats.json").write_text(
        (EX / "sqlcost_demo" / "stats.json").read_text("utf-8"), "utf-8")
    (root / "scenario.json").write_text(
        (EX / "dagconflict_demo" / "scenario.json").read_text("utf-8"),
        "utf-8")
    (root / "workload" / "queries.sql").write_text(
        (EX / "indexadvisor_demo" / "queries.sql").read_text("utf-8"),
        "utf-8")
    res = runner.invoke(perf_report, ["-d", str(root), "-F", "json"])
    assert res.exit_code == 0
    body = json.loads(res.output)
    assert set(body["sections"]) == {"plan", "slow_query", "cost", "dag",
                                     "index"}
    assert body["skipped"] == [] and body["failed"] == []
    res = runner.invoke(perf_report, ["-d", str(root), "--lang", "en"])
    assert res.exit_code == 0
    assert "Performance Health Report" in res.output
    # partial directory: missing inputs are named, present ones still run
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "plan.txt").write_text(
        (EX / "sqlperf_demo" / "plan.txt").read_text("utf-8"), "utf-8")
    (partial / "metrics.json").write_text("{broken", "utf-8")
    res = runner.invoke(perf_report, ["-d", str(partial), "-F", "json"])
    assert res.exit_code == 0
    body = json.loads(res.output)
    assert "plan" in body["sections"]
    assert any("slow_query" in f for f in body["failed"])
    assert "cost" in body["skipped"]
    # nothing recognized -> usage error
    empty = tmp_path / "empty"
    empty.mkdir()
    res = runner.invoke(perf_report, ["-d", str(empty)])
    assert res.exit_code == 2


def test_sqlcost_calibrate(tmp_path):
    runner = CliRunner()
    stats = str(EX / "sqlcost_demo" / "stats.json")
    q = str(EX / "sqlcost_demo" / "query.sql")
    actual = tmp_path / "m.json"
    actual.write_text('{"duration_s": 600, "scan_bytes": 1000000000}',
                      encoding="utf-8")
    res = runner.invoke(sqlcost, ["--sql-file", q, "-f", stats,
                                  "--calibrate", str(actual), "-F", "json"])
    assert res.exit_code == 0
    cal = json.loads(res.output)["calibration"]
    assert cal["duration"]["actual"] == 600 and cal["duration"]["ratio"] > 0
    assert cal["scan_bytes"]["actual"] == 1000000000
    res = runner.invoke(sqlcost, ["--sql-file", q, "-f", stats,
                                  "--calibrate", str(actual), "--lang", "en"])
    assert res.exit_code == 0 and "Calibration" in res.output
    # metrics without duration_s are a usage error, not a guess
    actual.write_text('{"scan_bytes": 5}', encoding="utf-8")
    res = runner.invoke(sqlcost, ["--sql-file", q, "-f", stats,
                                  "--calibrate", str(actual)])
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


def test_dagconflict_capacity_gap_line():
    runner = CliRunner()
    demo = EX / "dagconflict_demo" / "scenario.json"
    res = runner.invoke(dagconflict, ["-f", str(demo), "--lang", "en"])
    # the demo peaks over capacity -> the needed-capacity line shows
    assert res.exit_code == 0 and "To run as declared" in res.output
    res = runner.invoke(dagconflict, ["-f", str(demo)])
    assert "按声明起点跑完需要" in res.output


def test_dagconflict_deadline_gate(tmp_path):
    runner = CliRunner()
    demo = EX / "dagconflict_demo" / "scenario.json"
    scenario = json.loads(demo.read_text(encoding="utf-8"))
    for dag in scenario["dags"]:
        if dag["name"] == "etl_sales":
            dag["deadline"] = 30  # etl_sales finishes at 35 -> late
        else:
            dag["deadline"] = 500  # comfortably met
    tight = tmp_path / "tight.json"
    tight.write_text(json.dumps(scenario), encoding="utf-8")
    res = runner.invoke(dagconflict, ["-f", str(tight), "-F", "json"])
    body, _ = json.JSONDecoder().raw_decode(res.output)
    misses = body["deadline_misses"]
    assert len(misses) == 1 and misses[0]["dag"] == "etl_sales"
    # markdown names the late DAG; the gate trips
    res = runner.invoke(dagconflict, ["-f", str(tight), "--lang", "en"])
    assert res.exit_code == 0 and "Deadline misses" in res.output
    res = runner.invoke(dagconflict, ["-f", str(tight),
                                      "--fail-on-deadline-miss"])
    assert res.exit_code == 1 and "DEADLINE etl_sales" in res.output
    # no deadlines declared -> nothing reported, gate passes
    res = runner.invoke(dagconflict, ["-f", str(demo),
                                      "--fail-on-deadline-miss"])
    assert res.exit_code == 0


def test_sqlcost_batch_dir(tmp_path):
    runner = CliRunner()
    stats = str(EX / "sqlcost_demo" / "stats.json")
    qdir = tmp_path / "queries"
    qdir.mkdir()
    (qdir / "big.sql").write_text(
        (EX / "sqlcost_demo" / "query_full_scan.sql").read_text("utf-8"),
        encoding="utf-8")
    (qdir / "small.sql").write_text(
        (EX / "sqlcost_demo" / "query.sql").read_text("utf-8"),
        encoding="utf-8")
    (qdir / "broken.sql").write_text("not sql (((", encoding="utf-8")
    res = runner.invoke(sqlcost, ["-d", str(qdir), "-f", stats,
                                  "-F", "json"])
    assert res.exit_code == 0
    body = json.loads(res.output)
    assert [q["name"] for q in body["queries"]] == ["big.sql", "small.sql"]
    assert body["totals"]["scan_bytes"] > 0
    assert len(body["skipped"]) == 1 and "broken.sql" in body["skipped"][0]
    # total budget gate trips on the full-scan query
    res = runner.invoke(sqlcost, ["-d", str(qdir), "-f", stats,
                                  "--fail-over-total-scan-gb", "1"])
    assert res.exit_code == 1 and "BUDGET total scan" in res.output
    # both or neither of --sql-file/--dir is a usage error
    res = runner.invoke(sqlcost, ["-f", stats])
    assert res.exit_code == 2
    res = runner.invoke(sqlcost, ["-d", str(qdir), "-f", stats,
                                  "--sql-file", str(qdir / "big.sql")])
    assert res.exit_code == 2


def test_slowquery_ab_diff(tmp_path):
    runner = CliRunner()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({
        "name": "fast", "duration_s": 100, "scan_bytes": 1000,
        "stages": [{"stage": "s1", "task_max_s": 10, "task_median_s": 8},
                   {"stage": "s2", "task_max_s": 5, "task_median_s": 4}],
    }), encoding="utf-8")
    b.write_text(json.dumps({
        "name": "slow", "duration_s": 300, "scan_bytes": 1000,
        "stages": [{"stage": "s1", "task_max_s": 90, "task_median_s": 9},
                   {"stage": "s3", "task_max_s": 7, "task_median_s": 6}],
    }), encoding="utf-8")
    res = runner.invoke(slowquery, ["--diff", str(a), str(b), "-F", "json"])
    assert res.exit_code == 0
    delta = json.loads(res.output)
    assert delta["totals"]["duration_s"]["ratio"] == 3.0
    assert delta["stages"][0]["stage"] == "s1"
    assert delta["stages"][0]["task_max_s"]["ratio"] == 9.0
    assert delta["only_a"] == ["s2"] and delta["only_b"] == ["s3"]
    # markdown renders; mixing --diff with other inputs is a usage error
    res = runner.invoke(slowquery, ["--diff", str(a), str(b), "--lang", "en"])
    assert res.exit_code == 0 and "A/B diff" in res.output
    res = runner.invoke(slowquery, ["--diff", str(a), str(b), "-f", str(a)])
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


def test_dagconflict_misplaced_gate(tmp_path):
    runner = CliRunner()
    demo = EX / "dagconflict_demo" / "scenario.json"
    # demo declares a conflicting offset -> gate trips
    res = runner.invoke(dagconflict, ["-f", str(demo), "--place",
                                      "etl_users", "--fail-if-misplaced"])
    assert res.exit_code == 1 and "MISPLACED etl_users" in res.output
    # move the dag to the best offset -> gate passes
    scenario = json.loads(demo.read_text(encoding="utf-8"))
    best = json.loads(runner.invoke(
        dagconflict, ["-f", str(demo), "--place", "etl_users",
                      "-F", "json"]).output)["placement"]["best"]
    for dag in scenario["dags"]:
        if dag["name"] == "etl_users":
            dag["start"] = best["offset"]
    moved = tmp_path / "moved.json"
    moved.write_text(json.dumps(scenario), encoding="utf-8")
    res = runner.invoke(dagconflict, ["-f", str(moved), "--place",
                                      "etl_users", "--fail-if-misplaced"])
    assert res.exit_code == 0
    # without --place it is a usage error
    res = runner.invoke(dagconflict, ["-f", str(demo),
                                      "--fail-if-misplaced"])
    assert res.exit_code == 2


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
