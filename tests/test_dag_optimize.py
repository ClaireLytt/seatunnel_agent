"""Deterministic core tests for the DAG optimizer agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.dag_optimize import (
    optimize,
    parse_dag,
    render_markdown,
)
from seatunnel_agent.agents.data.dag_optimize.tools import dag_optimize

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "dagopt_demo"
        / "dag.json").read_text(encoding="utf-8")


def test_demo_redundant_edge_and_waves():
    result = optimize(parse_dag(DEMO))
    assert result.tasks == 7
    # extract_orders → join_wide is implied by extract_orders → clean_orders → join_wide
    assert [(r.up, r.down) for r in result.redundant] == [
        ("extract_orders", "join_wide")]
    assert result.redundant[0].via == [
        "extract_orders", "clean_orders", "join_wide"]
    assert result.batches == [
        ["extract_orders", "extract_users"],
        ["clean_orders", "clean_users"],
        ["join_wide"], ["agg_daily"], ["report"]]
    assert result.max_width == 2
    assert result.cycles == []


def test_demo_critical_path_durations_and_speedup():
    result = optimize(parse_dag(DEMO))
    assert result.critical_path == [
        "extract_orders", "clean_orders", "join_wide", "agg_daily", "report"]
    assert result.critical_duration == 35.0
    assert result.total_duration == 47.0
    assert result.speedup == pytest.approx(47 / 35, abs=0.01)


def test_text_arrow_lines_and_chain_detection():
    result = optimize(parse_dag("a -> b\nb -> c\nc -> d\na -> e\n"))
    # b, c, d form the tail of a single-in/single-out chain from b
    assert result.chains == [["b", "c", "d"]]
    assert result.redundant == []
    assert result.batches[0] == ["a"]


def test_chained_arrow_line():
    result = optimize(parse_dag("a -> b -> c"))
    assert result.batches == [["a"], ["b"], ["c"]]
    assert result.chains == [["a", "b", "c"]]


def test_csv_edges_and_isolated_node():
    result = optimize(parse_dag("up,down\nload,transform\ntransform,publish\naudit\n"))
    assert result.tasks == 4
    assert ["audit"] not in result.batches  # audit sits in wave 1 with load
    assert result.batches[0] == ["audit", "load"]


def test_cycle_excluded_with_warning():
    result = optimize(parse_dag("a -> b\nb -> a\nb -> c\n"))
    # c is downstream of the cycle, so it is unschedulable too
    assert set(result.cycles) == {"a", "b", "c"}
    assert result.warnings
    assert result.batches == []


def test_json_edges_object_form():
    result = optimize(parse_dag(
        '{"edges": [["x", "y"], {"up": "y", "down": "z"}]}'))
    assert result.batches == [["x"], ["y"], ["z"]]


def test_bad_inputs():
    with pytest.raises(ValueError):
        parse_dag("")
    with pytest.raises(ValueError):
        parse_dag('{"nope": 1}')
    with pytest.raises(ValueError):
        parse_dag('{"tasks": [{"deps": ["a"]}]}')
    with pytest.raises(ValueError):
        parse_dag('{"tasks": [{"name": "a", "duration": 0}]}')


def test_report_zh_en_and_tool():
    result = optimize(parse_dag(DEMO))
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "DAG 依赖优化" in zh and "关键路径" in zh
    assert "DAG Dependency Optimization" in en and "Critical path" in en
    assert "`extract_orders` → `join_wide`" in en
    md = dag_optimize(DEMO, lang="en")
    assert "ideal speedup" in md
    assert "must not be empty" in dag_optimize("  ")
    assert "bad input" in dag_optimize("{broken")
