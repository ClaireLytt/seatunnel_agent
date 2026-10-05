"""Tests for root-cause orchestration (rootcause.py + t2s-rootcause CLI):
attribution × lineage upstream × log-cluster correlation, sqlite e2e."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.text2sql.metrics import MetricStore
from seatunnel_agent.text2sql.partition import TimeRange
from seatunnel_agent.text2sql.rootcause import (
    render_root_cause_markdown,
    run_root_cause,
)
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

_DDL = """
CREATE TABLE dwd.sales(
  amount double COMMENT '金额',
  refund double COMMENT '退款',
  channel string COMMENT '渠道',
  dt string COMMENT '日期'
) COMMENT '销售明细';
"""

_METRICS = """
metrics:
  - name: gmv
    display_name: GMV
    table: dwd.sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel]
  - name: refund_amount
    display_name: 退款额
    table: dwd.sales
    expression: SUM(refund)
    time_column: dt
    dimensions: [channel]
  - name: refund_rate
    display_name: 退款率
    type: ratio
    numerator: refund_amount
    denominator: gmv
"""

# ods.raw_events -> dwd.sales (upstream chain for the lineage hop)
_WAREHOUSE_SQL = """
INSERT OVERWRITE TABLE dwd.sales
SELECT amount, refund, channel, dt FROM ods.raw_events;
"""

_JOB_LOG = """\
2026-03-08 02:11:00 ERROR [loader] java.io.IOException: write failed \
for table ods.raw_events partition dt=2026-03-08
    at com.example.Loader.run(Loader.java:42)
2026-03-08 02:11:05 ERROR [loader] java.io.IOException: write failed \
for table ods.raw_events partition dt=2026-03-08
    at com.example.Loader.run(Loader.java:42)
2026-03-08 03:00:00 WARN [other] unrelated slow query on dim.calendar
"""


@pytest.fixture()
def env(tmp_path):
    schema_store = SchemaStore(parse_ddl(_DDL))
    metric_store, errors = MetricStore.from_text(_METRICS, schema_store)
    assert not errors, errors

    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales(amount REAL, refund REAL, channel TEXT, dt TEXT)")
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", [
        (100.0, 5.0, "app", "2026-03-01"),
        (60.0, 5.0, "web", "2026-03-01"),
        (40.0, 10.0, "app", "2026-03-08"),   # GMV halves WoW, refunds up
        (40.0, 10.0, "web", "2026-03-08"),
    ])
    conn.commit()
    conn.close()

    # dwd.sales lives under db 'dwd' in the DDL but sqlite is flat: the
    # execute_fn strips the db prefix like the subscription runner does
    def execute_fn(sql: str):
        c = sqlite3.connect(db)
        try:
            cur = c.execute(sql.replace("dwd.sales", "sales"))
            cols = [d[0] for d in cur.description or []]
            return cols, [tuple(r) for r in cur.fetchall()]
        finally:
            c.close()

    lineage_dir = tmp_path / "warehouse_sql"
    lineage_dir.mkdir()
    (lineage_dir / "load_sales.sql").write_text(_WAREHOUSE_SQL, encoding="utf-8")

    log_dir = tmp_path / "job_logs"
    log_dir.mkdir()
    (log_dir / "loader.log").write_text(_JOB_LOG, encoding="utf-8")

    curr = TimeRange(start=date(2026, 3, 8), end=date(2026, 3, 8))
    prev = TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1))
    return schema_store, metric_store, execute_fn, lineage_dir, log_dir, curr, prev


def test_full_chain_additive(env) -> None:
    schema_store, metric_store, execute_fn, lineage_dir, log_dir, curr, prev = env
    report = run_root_cause(
        metric_store.get("gmv"), metric_store, schema_store, execute_fn,
        curr, prev, lineage_sql_dir=str(lineage_dir), log_dir=str(log_dir),
    )
    # attribution facts
    attr = report["attribution"]
    assert attr["type"] == "additive"
    assert attr["prev_total"] == pytest.approx(160.0)
    assert attr["curr_total"] == pytest.approx(80.0)
    # lineage hop found the upstream table
    assert report["upstream"] == ["ods.raw_events"]
    # log hop correlated the upstream table's error cluster
    assert report["suspects"], report.get("log_clusters")
    s = report["suspects"][0]
    assert s["tables"] == ["ods.raw_events"]
    assert s["level"] == "error" and s["count"] == 2
    # conclusions carry both facts
    joined = " ".join(report["conclusions"])
    assert "GMV" in joined and "疑似根因" in joined and "ods.raw_events" in joined


def test_ratio_metric_decomposed(env) -> None:
    schema_store, metric_store, execute_fn, *_, curr, prev = env[:3] + env[3:]
    report = run_root_cause(
        metric_store.get("refund_rate"), metric_store, schema_store,
        execute_fn, curr, prev,
    )
    attr = report["attribution"]
    assert attr["type"] == "ratio"
    assert "factor_split" in attr
    assert set(report["source_tables"]) == {"dwd.sales"}
    # optional hops skipped but stated
    assert report["upstream_skipped"] and report["logs_skipped"]


def test_no_suspects_is_stated(env, tmp_path) -> None:
    schema_store, metric_store, execute_fn, lineage_dir, _, curr, prev = env
    quiet = tmp_path / "quiet_logs"
    quiet.mkdir()
    (quiet / "ok.log").write_text(
        "2026-03-08 01:00:00 ERROR [x] boom in totally.unrelated_place\n",
        encoding="utf-8")
    report = run_root_cause(
        metric_store.get("gmv"), metric_store, schema_store, execute_fn,
        curr, prev, lineage_sql_dir=str(lineage_dir), log_dir=str(quiet),
    )
    assert report["suspects"] == []
    assert any("未发现" in c for c in report["conclusions"])


def test_render_markdown(env) -> None:
    schema_store, metric_store, execute_fn, lineage_dir, log_dir, curr, prev = env
    md = render_root_cause_markdown(run_root_cause(
        metric_store.get("gmv"), metric_store, schema_store, execute_fn,
        curr, prev, lineage_sql_dir=str(lineage_dir), log_dir=str(log_dir),
    ))
    assert "## 结论" in md and "## 上游血缘" in md and "## 疑似根因" in md


def test_cli_rootcause_sqlite(env, tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    _, _, _, lineage_dir, log_dir, _, _ = env
    # flat sqlite schema so the real executor can run unmodified SQL
    ddl = tmp_path / "ddl.sql"
    ddl.write_text(_DDL.replace("dwd.sales", "sales"), encoding="utf-8")
    metrics = tmp_path / "metrics.yaml"
    metrics.write_text(_METRICS.replace("dwd.sales", "sales"), encoding="utf-8")
    db = tmp_path / "sales.db"  # created by the fixture

    result = CliRunner().invoke(cli, [
        "t2s-rootcause", "--metric", "gmv",
        "--curr-start", "2026-03-08", "--compare", "wow",
        "--ddl", str(ddl), "--metrics", str(metrics),
        "--ds-type", "sqlite", "--database", str(db),
        "--log-dir", str(log_dir), "--lineage-dir", str(lineage_dir),
        "-F", "json",
    ])
    assert result.exit_code == 0, result.output
    assert '"curr_total": 80.0' in result.output
