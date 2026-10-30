"""Deterministic core tests for the SLA trace agent."""

from __future__ import annotations

import json
from pathlib import Path

import fastapi
import pytest

from seatunnel_agent.agents.data.sla_trace import (
    parse_instances,
    render_markdown,
    trace,
    trace_to_dict,
)

DEMO = Path(__file__).resolve().parents[1] / "examples" / "slatrace_demo" / "run.json"
DEMO_TEXT = DEMO.read_text(encoding="utf-8")


def test_parse_json_wrapper_and_csv():
    tasks = parse_instances(DEMO_TEXT)
    assert len(tasks) == 7
    csv_text = ("name,start,end,deps\n"
                "a,2024-01-01 00:00:00,2024-01-01 01:00:00,\n"
                "b,2024-01-01 01:00:00,2024-01-01 02:00:00,a\n")
    tasks = parse_instances(csv_text)
    assert tasks[1].deps == ("a",)


def test_critical_path_follows_last_finishing_dep():
    result = trace(parse_instances(DEMO_TEXT))
    assert result.target == "ads_sales_report"
    names = [s.task.name for s in result.path]
    # the slow ods_orders_sync chain is the critical path, not dwd_items
    assert names == ["ods_orders_sync", "dwd_orders", "dws_sales",
                     "ads_sales_report"]
    # dws_sales actually waited on dwd_orders (ends later than dwd_items)
    dws = next(s for s in result.path if s.task.name == "dws_sales")
    assert dws.blocking == "dwd_orders"


def test_top_delays_rank_the_slow_sync_first():
    result = trace(parse_instances(DEMO_TEXT))
    top = result.top_delays(3)
    assert top[0][0].task.name == "ods_orders_sync"


def test_sla_breach_and_ok():
    breached = trace(parse_instances(DEMO_TEXT),
                     deadline="2024-05-01 05:00:00")
    assert breached.breach_s == 600.0
    ok = trace(parse_instances(DEMO_TEXT), deadline="2024-05-01 06:00:00")
    assert ok.breach_s < 0


def test_render_markdown_bilingual():
    result = trace(parse_instances(DEMO_TEXT),
                   deadline="2024-05-01 05:00:00")
    zh = render_markdown(result, "zh")
    en = render_markdown(result, "en")
    assert "SLA 破线" in zh and "关键路径" in zh and "延迟大户" in zh
    assert "SLA BREACH" in en and "Critical path" in en


def test_explicit_target_and_missing_target():
    result = trace(parse_instances(DEMO_TEXT), target="dwd_items")
    assert [s.task.name for s in result.path] == ["ods_items_sync",
                                                  "dwd_items"]
    with pytest.raises(ValueError):
        trace(parse_instances(DEMO_TEXT), target="nope")


def test_cycle_is_truncated_with_warning():
    tasks = parse_instances(json.dumps([
        {"name": "a", "start": "2024-01-01 00:00:00",
         "end": "2024-01-01 01:00:00", "deps": ["b"]},
        {"name": "b", "start": "2024-01-01 01:00:00",
         "end": "2024-01-01 02:00:00", "deps": ["a"]},
    ]))
    result = trace(tasks)
    assert any("环" in w for w in result.warnings)


def test_to_dict_roundtrip():
    result = trace(parse_instances(DEMO_TEXT))
    data = trace_to_dict(result)
    assert data["target"] == "ads_sales_report"
    assert len(data["path"]) == 4
    assert data["path"][0]["name"] == "ods_orders_sync"


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client():
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.sla_trace.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_trace_text(api_client):
    r = api_client.post("/api/slatrace/trace", json={
        "text": DEMO_TEXT, "lang": "en", "report": True,
        "deadline": "2024-05-01 05:00:00"})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["breach_s"] == 600.0
    assert "Scheduling Delay Trace" in data["report"]


def test_api_trace_file_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("SLATRACE_API_ALLOWED_DIRS",
                       str(tmp_path / "only_here"))
    r = api_client.post("/api/slatrace/trace", json={"file": str(DEMO)})
    assert r.status_code == 403


def test_api_trace_requires_input(api_client):
    r = api_client.post("/api/slatrace/trace", json={})
    assert r.status_code == 400


def test_api_bad_input_is_400(api_client):
    r = api_client.post("/api/slatrace/trace", json={"text": "not,a,header\n1,2,3"})
    assert r.status_code == 400
