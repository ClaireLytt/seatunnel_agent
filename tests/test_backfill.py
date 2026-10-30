"""Deterministic core tests for the backfill planner agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.backfill import (
    compact_ranges,
    missing_slots,
    plan,
    plan_to_dict,
    render_markdown,
)
from seatunnel_agent.agents.data.data_freshness import parse_events, parse_rules
from seatunnel_agent.agents.data.data_lineage.loaders import from_sql_dir

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "backfill_demo"
DEMO_EVENTS = (DEMO_DIR / "updates.json").read_text(encoding="utf-8")
DEMO_RULES = (DEMO_DIR / "rules.json").read_text(encoding="utf-8")


def _demo_plan():
    graph, warnings = from_sql_dir(DEMO_DIR / "sql")
    assert warnings == []
    return plan(parse_events(DEMO_EVENTS), parse_rules(DEMO_RULES),
                graph=graph)


def test_demo_plan_gaps_cascade_and_batches():
    result = _demo_plan()
    by_table = {t.table: t for t in result.tables}
    assert by_table["ods.items"].missing == ["2024-05-04", "2024-05-05"]
    # dws.sales: its own 05-05 gap plus the cascaded 05-04 from ods.items
    assert by_table["dws.sales"].missing == ["2024-05-05"]
    assert by_table["dws.sales"].cascade == ["2024-05-04"]
    assert by_table["dws.sales"].from_upstream == ["ods.items"]
    # ads.sales_report: pure cascade (its own cadence is unknowable)
    assert by_table["ads.sales_report"].missing == []
    assert by_table["ads.sales_report"].cascade == ["2024-05-04",
                                                    "2024-05-05"]
    # topological batches: upstream first
    assert [t.batch for t in result.tables] == [1, 2, 3]
    assert [t.table for t in result.tables] == [
        "ods.items", "dws.sales", "ads.sales_report"]
    assert result.total_slots == 6
    assert ("ads.sales_report", "no_cadence") in result.skipped


def test_without_lineage_no_cascade():
    result = plan(parse_events(DEMO_EVENTS), parse_rules(DEMO_RULES))
    by_table = {t.table: t for t in result.tables}
    assert set(by_table) == {"ods.items", "dws.sales"}
    assert all(t.cascade == [] and t.batch == 1
               for t in result.tables)


def test_current_bucket_due_only_after_typical_arrival_plus_grace():
    events = parse_events(json.dumps(
        [{"table": "t", "updated": f"2024-05-0{d} 04:40:00"}
         for d in range(1, 5)]))
    # typical arrival 04:40 + 6h grace -> today due from 10:40
    early = plan(events, now="2024-05-05 10:00:00")
    assert early.tables == []
    due = plan(events, now="2024-05-05 11:00:00")
    assert due.tables[0].missing == ["2024-05-05"]


def test_since_clamps_the_window():
    result = plan(parse_events(DEMO_EVENTS), parse_rules(DEMO_RULES),
                  since="2024-05-05 00:00:00")
    by_table = {t.table: t for t in result.tables}
    assert by_table["ods.items"].missing == ["2024-05-05"]


def test_hourly_and_too_fine_grids():
    hourly = [f"2024-05-01 {h:02d}:05:00" for h in (0, 1, 2, 5)]
    slots = missing_slots(
        [__import__("datetime").datetime.fromisoformat(t) for t in hourly],
        3600.0, __import__("datetime").datetime(2024, 5, 1, 5, 30))
    assert slots is not None
    missing, granularity = slots
    assert granularity == "hour"
    assert missing == ["2024-05-01 03:00", "2024-05-01 04:00"]
    too_fine = missing_slots(
        [__import__("datetime").datetime(2024, 5, 1)], 60.0,
        __import__("datetime").datetime(2024, 5, 2))
    assert too_fine is None


def test_compact_ranges():
    assert compact_ranges(["2024-05-01", "2024-05-02", "2024-05-03",
                           "2024-05-05"]) == "2024-05-01..2024-05-03, 2024-05-05"
    assert compact_ranges(["2024-05-01 03:00"]) == "2024-05-01 03:00"


def test_commands_and_dict():
    result = _demo_plan()
    cmds = result.commands("rerun --table {table} --dt {date}")
    assert cmds[0] == "rerun --table ods.items --dt 2024-05-04"
    assert len(cmds) == 6
    data = plan_to_dict(result)
    assert data["batches"] == 3 and data["total_slots"] == 6
    assert data["tables"][0]["table"] == "ods.items"


def test_render_markdown_bilingual_and_all_ok():
    result = _demo_plan()
    zh = render_markdown(result, "zh", cmd_template="x {table} {date}")
    en = render_markdown(result, "en")
    assert "补数计划" in zh and "级联重跑" in zh and "x ods.items 2024-05-04" in zh
    assert "Backfill Plan" in en and "re-run" in en
    clean = plan(parse_events(json.dumps(
        [{"table": "t", "updated": f"2024-05-0{d} 01:00:00"}
         for d in range(1, 6)])))
    assert "无需补数" in render_markdown(clean, "zh")


def test_bad_inputs():
    with pytest.raises(ValueError):
        plan({})
