"""Deterministic core tests for the migration assessor agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.pipeline_migrate import (
    assess_dir,
    assess_text,
    render_markdown,
)
from seatunnel_agent.agents.data.pipeline_migrate.tools import pipeline_migrate

DEMO_DIR = (Path(__file__).resolve().parents[1] / "examples"
            / "pipemigrate_demo")


def _by_job():
    report = assess_dir(DEMO_DIR)
    return report, {j.job: j for j in report.jobs}


def test_demo_targets():
    _, by = _by_job()
    assert by["sync_orders.sh"].target == "seatunnel"
    assert by["sync_orders.sh"].reasons == ["plain_sync"]
    assert by["build_sales.hql"].target == "spark_sql"
    assert by["stream_clicks.py"].target == "flink"
    assert by["run_all.sh"].target == "scheduler"
    assert by["run_all.sh"].reasons == ["orchestration_only"]


def test_demo_risks_and_metrics():
    _, by = _by_job()
    sales = by["build_sales.hql"]
    assert sales.statements == 2
    assert sales.joins == 1
    assert "dynamic_sql" in sales.risks  # ${hiveconf:dt}
    assert "shell_logic" in by["run_all.sh"].risks


def test_jobs_sorted_easiest_first_and_counts():
    report, _ = _by_job()
    scores = [j.score for j in report.jobs]
    assert scores == sorted(scores)
    counts = report.counts()
    assert counts == {"seatunnel": 1, "spark_sql": 2, "flink": 1,
                      "scheduler": 1}
    assert sum(report.effort_counts().values()) == 5


def test_table_deps_and_migration_order():
    report, by = _by_job()
    assert by["load_users.sql"].produces == ["ods.users"]
    assert "staging.users_raw" in by["load_users.sql"].consumes
    # build_sales reads ods.users which load_users produces
    assert "ods.users" in by["build_sales.hql"].consumes
    assert "dws.sales" in by["build_sales.hql"].produces
    # producer migrates in an earlier wave than its consumer
    wave_of = {j: i for i, wave in enumerate(report.migration_order)
               for j in wave}
    assert wave_of["load_users.sql"] < wave_of["build_sales.hql"]
    # the shared table names the producer and its consumers
    shared = {s["table"]: s for s in report.shared_tables}
    assert shared["ods.users"]["producer"] == "load_users.sql"
    assert shared["ods.users"]["consumers"] == ["build_sales.hql"]


def test_seatunnel_stub_from_sqoop_args():
    _, by = _by_job()
    stub = by["sync_orders.sh"].stub
    assert 'url = "jdbc:mysql://db/shop"' in stub
    assert 'query = "SELECT * FROM orders"' in stub
    assert 'path = "/warehouse/ods/orders"' in stub
    assert 'job.mode = "BATCH"' in stub
    # non-seatunnel targets carry no stub
    assert by["build_sales.hql"].stub == ""
    from seatunnel_agent.agents.data.pipeline_migrate import render_markdown
    report, _ = _by_job()
    assert "```hocon" in render_markdown(report, lang="en")


def test_single_script_text():
    report = assess_text("legacy.sql",
                         "SELECT a FROM t1, t2 WHERE t1.id = t2.id(+);")
    job = report.jobs[0]
    assert job.kind == "sql"
    assert "oracle_join" in job.risks
    assert job.target == "spark_sql"


def test_effort_scales_with_complexity():
    small = assess_text("s.sql", "INSERT INTO t SELECT * FROM s;").jobs[0]
    big_sql = "\n".join(
        f"INSERT OVERWRITE TABLE t{i} SELECT * FROM a{i} "
        f"JOIN b{i} ON a{i}.k = b{i}.k;" for i in range(10))
    big = assess_text("b.sql", big_sql).jobs[0]
    assert small.effort == "S"
    assert big.effort == "L"
    assert big.score > small.score


def test_bad_inputs(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        assess_dir(DEMO_DIR / "nope")
    with pytest.raises(ValueError, match="empty script"):
        assess_text("x.sql", "  ")
    (tmp_path / "readme.txt").write_text("not a script", encoding="utf-8")
    with pytest.raises(ValueError, match="no scripts"):
        assess_dir(tmp_path)


def test_report_zh_en_and_tool():
    report, _ = _by_job()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "Pipeline 迁移评估" in zh and "目标引擎" in zh
    assert "Pipeline Migration Assessment" in en and "SeaTunnel" in en
    md = pipeline_migrate(scripts_dir=str(DEMO_DIR), lang="en")
    assert "easiest first" in md
    assert "provide scripts_dir" in pipeline_migrate()
    assert "not a directory" in pipeline_migrate(scripts_dir="no/such/dir")
