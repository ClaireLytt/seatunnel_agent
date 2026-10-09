# -*- coding: utf-8 -*-
"""Tests for the query cost advisor.

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from seatunnel_agent.cost_advisor import (
    analyze_cost,
    render_markdown,
    report_to_dict,
)
from seatunnel_agent.cost_advisor.analyzer import normalize_template


def _rec(sql: str, tables: list[str], ms: int = 1000, rows: int = 10,
         status: str = "success") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_query": "q",
        "matched_tables": tables,
        "generated_sql": sql,
        "exec_time_ms": ms,
        "row_count": rows,
        "status": status,
    }


def _write_qlog(tmp_path, records) -> str:
    p = tmp_path / "qlog.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return str(p)


def test_normalize_template_masks_literals():
    a = normalize_template("SELECT * FROM t WHERE dt = '2026-09-01' LIMIT 100")
    b = normalize_template("SELECT * FROM t WHERE dt = '2026-09-02' LIMIT 500")
    assert a == b


def test_analyze_aggregates_by_template(tmp_path):
    sql = "SELECT dt, SUM(amt) FROM dws_pay_df WHERE dt = '{d}' GROUP BY dt"
    records = [
        _rec(sql.format(d="2026-09-01"), ["dws_pay_df"], ms=2000),
        _rec(sql.format(d="2026-09-02"), ["dws_pay_df"], ms=4000),
        _rec("SELECT COUNT(*) FROM dim_user", ["dim_user"], ms=100),
    ]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    assert report.success_count == 3
    assert report.total_ms == 6100
    top = report.top_queries[0]
    assert top.runs == 2 and top.total_ms == 6000 and top.avg_ms == 3000
    assert top.tables == ["dws_pay_df"]


def test_failed_records_excluded(tmp_path):
    records = [
        _rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"], status="error"),
        _rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"], status="rejected"),
        _rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"]),
    ]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    assert report.success_count == 1


def test_missing_partition_filter_flagged(tmp_path):
    records = [
        _rec("SELECT COUNT(*) FROM dwd_log", ["dwd_log"], ms=9000),
        _rec("SELECT COUNT(*) FROM dwd_log WHERE dt = '2026-09-01'",
             ["dwd_log"], ms=100),
    ]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    missing = report.no_partition_filter
    assert len(missing) == 1
    assert missing[0].total_ms == 9000


def test_table_costs_ranked(tmp_path):
    records = [
        _rec("SELECT 1 FROM a WHERE dt='2026-09-01'", ["a"], ms=100),
        _rec("SELECT 2 FROM b WHERE dt='2026-09-01'", ["b"], ms=5000),
    ]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    assert report.table_costs[0].table == "b"


def test_skew_pattern_tagging(tmp_path):
    pytest.importorskip("sqlglot")
    sql = "SELECT COUNT(DISTINCT uid) FROM dwd_log WHERE dt='2026-09-01'"
    report = analyze_cost(_write_qlog(tmp_path, [_rec(sql, ["dwd_log"])]),
                          scan_patterns=True)
    assert report.top_queries[0].skew_categories  # at least one rule fires


def test_render_markdown_zh_en_and_empty(tmp_path):
    report = analyze_cost(_write_qlog(tmp_path, []))
    zh = render_markdown(report, "zh")
    assert "查询成本顾问" in zh and "没有审计记录" in zh

    records = [_rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"])]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    en = render_markdown(report, "en")
    assert "Query Cost Advisor" in en and "| t | 1 | 1000 |" in en


def test_report_to_dict_serializable(tmp_path):
    records = [_rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"])]
    report = analyze_cost(_write_qlog(tmp_path, records), scan_patterns=False)
    json.dumps(report_to_dict(report))


def test_cli_cost_json(tmp_path):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    qlog = _write_qlog(
        tmp_path, [_rec("SELECT 1 FROM t WHERE dt='2026-09-01'", ["t"])])
    runner = CliRunner()
    result = runner.invoke(cli, ["cost", "--qlog", qlog, "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["success_count"] == 1
