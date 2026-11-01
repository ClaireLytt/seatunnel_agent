"""Tests for the sla_board agent (board / report / CLI / tool / API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.sample_profile import parse_rows
from seatunnel_agent.agents.data.sla_board import (
    build_board,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "slaboard_demo" / "runs.csv"


def _demo_board(**kw):
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return build_board(headers, rows, **kw)


# ------------------------------------------------------------------- board

def test_demo_board_metrics():
    board = _demo_board()
    assert board.runs_total == 18 and board.misses_total == 5
    by = {t.task: t for t in board.tasks}
    worst = by["dws_orders_daily"]
    assert worst.rate == pytest.approx(1 / 3)
    assert worst.live_streak == 4 and worst.max_streak == 4
    assert worst.worst_late_min == 130.0
    assert by["dim_users_sync"].rate == 1.0
    assert board.tasks[0].task == "dws_orders_daily"   # worst first


def test_demo_findings_graded():
    board = _demo_board()
    codes = {(f.code, f.task, f.severity) for f in board.findings}
    assert ("SL001", "dws_orders_daily", "high") in codes
    assert ("SL002", "dws_orders_daily", "high") in codes
    assert ("SL003", "dws_orders_daily", "medium") in codes
    assert ("SL001", "ads_user_report", "medium") in codes
    assert all(f.task != "dim_users_sync" for f in board.findings)


def test_past_midnight_and_iso_times():
    csv = ("task,date,deadline,finish\n"
           "t,2026-10-01,23:30,25:10\n"
           "t,2026-10-02,2026-10-03T01:00:00,2026-10-03T00:40:00\n")
    headers, rows = parse_rows(csv)
    board = build_board(headers, rows)
    (t,) = board.tasks
    assert t.misses == 1 and t.worst_late_min == 100.0


def test_mixed_time_formats_in_one_row_raise():
    # review finding: HH:MM and ISO live on different scales — a mixed
    # row must refuse loudly instead of scoring garbage
    csv = ("task,date,deadline,finish\n"
           "t,2026-10-01,07:00,2026-10-01T07:20:00\n")
    headers, rows = parse_rows(csv)
    with pytest.raises(ValueError, match="mix HH:MM"):
        build_board(headers, rows)


def test_streak_resets_on_hit():
    csv = ("task,date,deadline,finish\n"
           "t,2026-10-01,07:00,08:00\n"
           "t,2026-10-02,07:00,08:00\n"
           "t,2026-10-03,07:00,06:00\n"
           "t,2026-10-04,07:00,08:00\n")
    headers, rows = parse_rows(csv)
    (t,) = build_board(headers, rows).tasks
    assert t.max_streak == 2 and t.live_streak == 1


def test_bad_inputs():
    headers, rows = parse_rows("task,date,deadline,finish\nt,d,07:00,xx\n")
    with pytest.raises(ValueError, match="cannot parse time"):
        build_board(headers, rows)
    h2, r2 = parse_rows("task,deadline\nt,07:00\n")
    with pytest.raises(ValueError, match="missing"):
        build_board(h2, r2)
    h3, r3 = parse_rows(DEMO.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="target"):
        build_board(h3, r3, target=0.3)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    board = _demo_board()
    zh = render_markdown(board, lang="zh")
    en = render_markdown(board, lang="en")
    assert "SLA 达成看板" in zh and "连续破线" in zh
    assert "SLA Board" in en and "live miss streak" in en
    headers, rows = parse_rows(
        "task,date,deadline,finish\nt,2026-10-01,07:00,06:00\n")
    clean = render_markdown(build_board(headers, rows), lang="en")
    assert "SLA stands" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_gate_and_history(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["slaboard", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "SLA 达成看板" in res.output
    res = runner.invoke(cli, ["slaboard", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"misses_total": 5' in res.output
    res = runner.invoke(cli, ["slaboard", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    ledger = tmp_path / "sla.jsonl"
    res = runner.invoke(cli, ["slaboard", "-f", str(DEMO),
                              "--history", str(ledger)])
    assert res.exit_code == 0
    entry = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["misses"] == 5 and entry["runs"] == 18


def test_cli_trend_requires_history():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["slaboard", "-f", str(DEMO),
                                   "--trend", "3"])
    assert res.exit_code != 0


def test_cli_fail_on_trend(tmp_path):
    from seatunnel_agent.cli import cli

    ledger = tmp_path / "sla.jsonl"
    ledger.write_text('{"misses": 1}\n{"misses": 3}\n', encoding="utf-8")
    res = CliRunner().invoke(cli, ["slaboard", "-f", str(DEMO),
                                   "--history", str(ledger),
                                   "--trend", "3", "--fail-on-trend"])
    assert res.exit_code == 1
    assert "misses" in res.output


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.sla_board.tools import sla_board

    out = sla_board(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "SLA Board" in out and "dws_orders_daily" in out
    assert "must not be empty" in sla_board("  ")
    assert "bad input" in sla_board("task,date\nt,d\n")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.sla_board.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_score_and_health():
    client = _client()
    assert client.get("/api/slaboard/health").status_code == 200
    resp = client.post("/api/slaboard/score", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["misses_total"] == 5
    assert "SLA Board" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/slaboard/score",
                       json={"data_text": "task,date\nt,d\n"})
    assert resp.status_code == 400
