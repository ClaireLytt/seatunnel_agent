"""Deterministic core tests for the DAG conflict detector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.dag_conflict import (
    parse_scenario,
    render_markdown,
    simulate,
)
from seatunnel_agent.agents.data.dag_conflict.tools import dag_conflict

DEMO = (Path(__file__).resolve().parents[1] / "examples"
        / "dagconflict_demo" / "scenario.json").read_text(encoding="utf-8")


def _report():
    return simulate(parse_scenario(DEMO))


def test_demo_over_capacity_window():
    report = _report()
    # timeline: transform(6 slots,10-30) overlaps merge_u(6 slots,15-30)
    # → 12 slots > 10 in [15, 30)
    assert report.peak_slots == 12
    assert len(report.windows) == 1
    w = report.windows[0]
    assert (w.start, w.end) == (15.0, 30.0)
    assert w.peak_slots == 12
    assert ("etl_sales", "transform") in w.tasks
    assert ("etl_users", "merge_u") in w.tasks


def test_demo_write_conflict_and_suggestion():
    report = _report()
    assert len(report.write_conflicts) == 1
    c = report.write_conflicts[0]
    assert c["table"] == "dws.sales"
    assert {c["a"], c["b"]} == {"etl_sales:transform", "etl_users:merge_u"}
    assert c["overlap"] == [15.0, 30.0]
    # the stagger suggestion is re-simulated: delaying etl_users past the
    # window clears every over-capacity window
    s = report.suggestion
    assert s["dag"] == "etl_users"
    assert s["delay"] == 25  # ceil(30 - start 5)
    assert s["peak_slots_before"] == 12
    assert s["peak_slots_after"] <= 10
    assert s["windows_after"] == 0


def test_fits_capacity_reports_clean():
    scenario = json.loads(DEMO)
    scenario["capacity"]["slots"] = 20
    scenario["dags"][1]["tasks"][1].pop("writes")
    report = simulate(parse_scenario(json.dumps(scenario)))
    assert report.windows == [] and report.write_conflicts == []
    assert report.suggestion == {}
    assert "共存" in render_markdown(report, lang="zh")


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty scenario"):
        parse_scenario("  ")
    with pytest.raises(ValueError, match="'dags' list"):
        parse_scenario('{"capacity": {"slots": 5}}')
    with pytest.raises(ValueError, match="slots must be"):
        parse_scenario('{"capacity": {}, "dags": [{"name": "a", '
                       '"tasks": [{"name": "t"}]}]}')
    with pytest.raises(ValueError, match="cycle"):
        simulate(parse_scenario(
            '{"capacity": {"slots": 5}, "dags": [{"name": "a", "tasks": '
            '[{"name": "x", "deps": ["y"]}, {"name": "y", "deps": ["x"]}]}]}'))


def test_report_zh_en_and_tool():
    report = _report()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "多 DAG 并发冲突" in zh and "错峰建议" in zh and "写写冲突" in zh
    assert "Concurrent DAG Conflicts" in en and "re-simulated" in en
    md = dag_conflict(DEMO, lang="en")
    assert "dws.sales" in md
    assert "must not be empty" in dag_conflict(" ")
    assert "bad input" in dag_conflict("{broken")


def test_api_place_admission():
    """'place' adds the placement payload and section; unknown dag 400s."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.dag_conflict import api as dc_api

    app = FastAPI()
    app.include_router(dc_api.router)
    client = TestClient(app)
    res = client.post("/api/dagconflict/simulate", json={
        "text": DEMO, "place": "etl_users", "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    best = body["result"]["placement"]["best"]
    assert best["windows"] == 0 and best["write_conflicts"] == 0
    assert "Admission check" in body["report"]
    res = client.post("/api/dagconflict/simulate", json={
        "text": DEMO, "place": "nope"})
    assert res.status_code == 400
