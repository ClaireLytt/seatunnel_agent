"""Deterministic core tests for the slow-query diagnoser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.slow_query import (
    diagnose,
    parse_baseline,
    parse_metrics,
    render_markdown,
)
from seatunnel_agent.agents.data.slow_query.tools import slow_query

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "slowquery_demo"
METRICS = (DEMO_DIR / "metrics.json").read_text(encoding="utf-8")
BASELINE = (DEMO_DIR / "baseline.jsonl").read_text(encoding="utf-8")


def _diag():
    return diagnose(parse_metrics(METRICS), parse_baseline(BASELINE))


def test_demo_causes_ranked():
    diag = _diag()
    codes = [c.code for c in diag.causes]
    # skew dominates: (1250-110)/1800 ≈ 63% share, ranked first
    assert codes[0] == "SQ001"
    assert diag.causes[0].share == pytest.approx((1250 - 110) / 1800,
                                                 abs=1e-3)
    assert diag.causes[0].refer == "data_skew"
    # scan 850GB vs median 405GB ≈ 2.1x → blow-up fires
    assert "SQ002" in codes
    # 30 GiB spill fires; GC 5% and queue 6.7% stay silent
    assert "SQ003" in codes
    assert "SQ004" not in codes and "SQ005" not in codes
    # shares are non-increasing
    shares = [c.share for c in diag.causes]
    assert shares == sorted(shares, reverse=True)


def test_regression_header():
    diag = _diag()
    assert diag.baseline_median_s == 430
    assert diag.regression == pytest.approx(1800 / 430, abs=0.01)
    # no baseline → no regression figure
    assert diagnose(parse_metrics(METRICS)).regression == 0.0


def test_queue_gc_and_small_files_rules():
    metrics = json.dumps({
        "duration_s": 100, "gc_s": 30, "queue_s": 40,
        "stages": [{"stage": "s", "task_max_s": 1, "task_median_s": 1,
                    "tasks": 500, "input_bytes": 500 * 1024 * 1024}]})
    diag = diagnose(parse_metrics(metrics))
    codes = {c.code for c in diag.causes}
    assert {"SQ004", "SQ005", "SQ006"} <= codes
    assert "SQ001" not in codes


def test_clean_run_fires_nothing():
    metrics = json.dumps({
        "duration_s": 100,
        "stages": [{"stage": "s", "task_max_s": 12, "task_median_s": 10}]})
    diag = diagnose(parse_metrics(metrics))
    assert diag.causes == []
    assert "没有规则命中" in render_markdown(diag, lang="zh")


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty metrics"):
        parse_metrics(" ")
    with pytest.raises(ValueError, match="duration_s"):
        parse_metrics('{"name": "q"}')
    with pytest.raises(ValueError, match="JSON object"):
        parse_metrics("[1, 2]")


def test_report_zh_en_and_tool():
    diag = _diag()
    zh = render_markdown(diag, lang="zh")
    en = render_markdown(diag, lang="en")
    assert "慢查询根因" in zh and "处方" in zh and "4.19x" in zh
    assert "Slow-Query Root Cause" in en and "straggler" in en
    md = slow_query(METRICS, baseline=BASELINE, lang="en")
    assert "SQ001" in md
    assert "must not be empty" in slow_query(" ")
    assert "bad input" in slow_query("{broken")


def test_incident_note_wiring(monkeypatch):
    """API llm=true appends the drafted note; the LLM call is stubbed."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.slow_query import advisor_llm
    from seatunnel_agent.agents.data.slow_query import api as sq_api

    monkeypatch.setattr(advisor_llm, "incident_note",
                        lambda diag, lang="zh": "NOTE-" + str(len(diag.causes)))
    app = FastAPI()
    app.include_router(sq_api.router)
    client = TestClient(app)
    metrics = (Path(__file__).resolve().parents[1] / "examples"
               / "slowquery_demo" / "metrics.json").read_text("utf-8")
    res = client.post("/api/slowquery/diagnose",
                      json={"metrics": metrics, "llm": True,
                            "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["incident_note"].startswith("NOTE-")
    assert "Incident note draft" in body["report"]
    # default path untouched
    res = client.post("/api/slowquery/diagnose", json={"metrics": metrics})
    assert "incident_note" not in res.json()["result"]
