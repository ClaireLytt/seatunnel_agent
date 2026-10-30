"""Deterministic core tests for the rerun planner agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.rerun_plan import (
    parse_dag,
    plan_rerun,
    render_markdown,
)
from seatunnel_agent.agents.data.rerun_plan.tools import rerun_plan

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "rerun_demo"
        / "dag.json").read_text(encoding="utf-8")


def test_failed_leaf_only_itself():
    result = plan_rerun(parse_dag(DEMO), "report")
    assert [(t.task, t.batch, t.reason) for t in result.tasks] == [
        ("report", 1, "failed")]
    assert result.blast_radius == pytest.approx(1 / 8)
    assert "join_wide" in result.untouched


def test_failed_mid_cascades_downstream_only():
    result = plan_rerun(parse_dag(DEMO), "clean_orders")
    assert [t.task for t in result.tasks] == [
        "clean_orders", "join_wide", "agg_daily", "report"]
    assert [t.batch for t in result.tasks] == [1, 2, 3, 4]
    # siblings and upstream stay untouched
    assert set(result.untouched) == {
        "extract_orders", "extract_users", "clean_users", "audit_users"}
    by = {t.task: t for t in result.tasks}
    assert by["join_wide"].reason == "downstream"
    assert by["join_wide"].from_failed == ["clean_orders"]


def test_two_failures_merge_and_batch_together():
    result = plan_rerun(parse_dag(DEMO), "clean_orders, clean_users")
    by = {t.task: t for t in result.tasks}
    assert by["clean_orders"].batch == 1 and by["clean_users"].batch == 1
    assert by["join_wide"].from_failed == ["clean_orders", "clean_users"]
    assert by["audit_users"].from_failed == ["clean_users"]
    assert result.untouched == ["extract_orders", "extract_users"]


def test_succeeded_inside_closure_is_flagged_stale():
    result = plan_rerun(parse_dag(DEMO), "clean_orders",
                        succeeded="join_wide, extract_users")
    by = {t.task: t for t in result.tasks}
    assert by["join_wide"].stale_success is True
    assert by["agg_daily"].stale_success is False
    # succeeded outside the closure simply stays untouched
    assert "extract_users" in result.untouched


def test_failed_root_through_failed_root():
    # a -> b -> c, both a and b failed: c descends from both
    result = plan_rerun(parse_dag("a -> b\nb -> c"), ["a", "b"])
    by = {t.task: t for t in result.tasks}
    assert by["b"].reason == "failed"
    assert by["c"].from_failed == ["a", "b"]


def test_capacity_aware_makespan():
    dag = ('{"tasks":[{"name":"a","duration":10},'
           '{"name":"b","deps":["a"],"duration":3},'
           '{"name":"c","deps":["a"],"duration":7},'
           '{"name":"d","deps":["b","c"],"duration":2}]}')
    result = plan_rerun(parse_dag(dag), "a")
    # 1 slot = serial sum; 2 slots overlap b/c; monotone non-increasing
    assert result.makespans["1"] == 22.0
    assert result.makespans["2"] == 19.0
    assert result.makespans["4"] == 19.0
    md = render_markdown(result, lang="en")
    assert "1 slot(s) → 22" in md
    # upstream outside the rerun set does not gate the simulated start
    partial = plan_rerun(parse_dag(dag), "b")
    assert partial.makespans["1"] == 5.0  # b(3) + d(2)


def test_independent_recovery_groups():
    # clean_orders cascades to the sales chain; audit path fails separately
    result = plan_rerun(parse_dag(DEMO), "clean_orders, audit_users")
    assert result.groups == [
        ["agg_daily", "clean_orders", "join_wide", "report"],
        ["audit_users"]]
    md = render_markdown(result, lang="zh")
    assert "可独立恢复的分组" in md
    # a single connected rerun set renders no group section
    single = plan_rerun(parse_dag(DEMO), "clean_orders")
    assert len(single.groups) == 1
    assert "可独立恢复" not in render_markdown(single, lang="zh")


def test_duration_aware_eta():
    dag = ('{"tasks":[{"name":"a","duration":10},'
           '{"name":"b","deps":["a"],"duration":3},'
           '{"name":"c","deps":["a"],"duration":7},'
           '{"name":"d","deps":["b","c"],"duration":2}]}')
    result = plan_rerun(parse_dag(dag), "a")
    # batch1 a=10, batch2 max(b=3, c=7)=7, batch3 d=2
    assert result.batch_etas == [10.0, 7.0, 2.0]
    assert result.total_eta == 19.0
    md = render_markdown(result, lang="en")
    assert "Estimated duration 19" in md


def test_statuses_json_and_lines():
    from seatunnel_agent.agents.data.rerun_plan import parse_statuses

    failed, ok = parse_statuses(
        '{"clean_orders":"failed","join_wide":"success",'
        '"report":"queued","agg_daily":"up_for_retry"}')
    assert failed == ["clean_orders", "agg_daily"]
    assert ok == ["join_wide"]
    failed, ok = parse_statuses(
        "clean_orders=failed\n# comment\njoin_wide=success\n")
    assert failed == ["clean_orders"] and ok == ["join_wide"]
    with pytest.raises(ValueError, match="no failed"):
        parse_statuses('{"a":"success"}')
    with pytest.raises(ValueError, match="task=state"):
        parse_statuses("just-a-task-name")


def test_statuses_drive_the_plan_via_tool():
    md = rerun_plan(DEMO, statuses='{"clean_orders":"failed",'
                                   '"join_wide":"success"}', lang="en")
    assert "stale inputs (had succeeded)" in md
    assert "must not be empty" in rerun_plan(DEMO)


def test_bad_inputs():
    graph = parse_dag(DEMO)
    with pytest.raises(ValueError, match="no failed"):
        plan_rerun(graph, "")
    with pytest.raises(ValueError, match="unknown task"):
        plan_rerun(graph, "nope")
    with pytest.raises(ValueError, match="both failed and succeeded"):
        plan_rerun(graph, "report", succeeded="report")


def test_report_zh_en_and_tool():
    result = plan_rerun(parse_dag(DEMO), "clean_orders")
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en", cmd_template="rerun {task}")
    assert "任务重跑计划" in zh and "影响面" in zh
    assert "Rerun Plan" in en and "rerun clean_orders" in en
    md = rerun_plan(DEMO, "clean_orders", lang="en")
    assert "blast radius" in md
    assert "must not be empty" in rerun_plan("", "x")
    assert "must not be empty" in rerun_plan(DEMO, " ")
    assert "bad input" in rerun_plan(DEMO, "nope")
