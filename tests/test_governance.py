"""Tests for the governance advisor (lineage graph × query audit log)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlglot")

from seatunnel_agent.data_lineage.governance import (
    analyze_governance,
    load_qlog_records,
    render_governance_markdown,
)
from seatunnel_agent.data_lineage.loaders import build_graph


@pytest.fixture()
def graph(tmp_path):
    sql_dir = tmp_path / "warehouse"
    sql_dir.mkdir()
    (sql_dir / "etl.sql").write_text(
        # raw -> dwd -> two marts; mart_cold has no downstream and is never queried
        "INSERT OVERWRITE TABLE dwd.orders SELECT * FROM raw.orders_src;\n"
        "INSERT OVERWRITE TABLE ads.mart_hot SELECT * FROM dwd.orders;\n"
        "INSERT OVERWRITE TABLE ads.mart_cold SELECT * FROM dwd.orders;\n",
        encoding="utf-8",
    )
    g, warnings = build_graph(sql_dir=sql_dir)
    assert not warnings
    return g


def _rec(tables, status="success", error="", age_days=1):
    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat(
        timespec="seconds")
    return {"timestamp": ts, "matched_tables": tables, "status": status,
            "error": error}


def test_analyze_governance(graph) -> None:
    records = [
        _rec(["ads.mart_hot"]),
        _rec(["ads.mart_hot"]),
        _rec(["dwd.orders"], status="rejected",
             error="Partitioned table(s) missing partition filter"),
        _rec(["dwd.orders"], status="error", error="timeout"),
        _rec(["ads.mart_hot"], age_days=90),  # outside window when days=30
    ]
    report = analyze_governance(graph, [r for r in records if True][:4], days=30)
    assert report.graph_tables >= 4
    assert "ads.mart_cold" in report.decommission_candidates
    assert "ads.mart_hot" not in report.decommission_candidates
    assert report.hot_tables[0] == ("ads.mart_hot", 2)
    assert ("dwd.orders", 2) in report.rejection_prone
    assert ("dwd.orders", 1) in report.partition_filter_offenders
    assert "ads.mart_hot" in report.queried_leaves

    text = render_governance_markdown(report)
    assert "下线候选" in text and "ads.mart_cold" in text
    assert "只出建议" in text


def test_bare_name_matching(graph) -> None:
    # qlog recorded the bare table name -> still counts as queried
    report = analyze_governance(graph, [_rec(["mart_cold"])], days=30)
    assert "ads.mart_cold" not in report.decommission_candidates


def test_load_qlog_records_window(tmp_path) -> None:
    path = tmp_path / "q.jsonl"
    lines = [
        json.dumps(_rec(["t1"], age_days=1)),
        json.dumps(_rec(["t2"], age_days=45)),
        "not json",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    records = load_qlog_records(path, days=30)
    assert len(records) == 1
    assert records[0]["matched_tables"] == ["t1"]
    assert load_qlog_records(tmp_path / "missing.jsonl") == []


def test_cli_govern(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    sql_dir = tmp_path / "wh"
    sql_dir.mkdir()
    (sql_dir / "a.sql").write_text(
        "INSERT OVERWRITE TABLE ads.m SELECT * FROM dwd.o;\n", encoding="utf-8")
    qlog = tmp_path / "q.jsonl"
    qlog.write_text(json.dumps(_rec(["ads.m"])) + "\n", encoding="utf-8")
    out_file = tmp_path / "report.md"

    r = CliRunner().invoke(cli, [
        "govern", "--sql-dir", str(sql_dir), "--qlog", str(qlog),
        "--output", str(out_file),
    ])
    assert r.exit_code == 0, r.output
    assert "数据治理建议报告" in r.output
    assert out_file.is_file()
