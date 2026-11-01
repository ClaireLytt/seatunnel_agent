"""Tests for the task-failure agent (53): classifier, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.task_failure import (
    classify_failures,
    parse_failures,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "taskfailure_demo" / "failures.json"
EXPORT = DEMO.read_text("utf-8")


def _classify(text: str = EXPORT):
    return classify_failures(parse_failures(text))


# ── classifier ───────────────────────────────────────────────────────

def test_demo_cause_distribution():
    result = _classify()
    assert result.total == 7
    assert result.causes["dependency_missing"] == 3
    assert set(result.causes) == {"dependency_missing", "resource",
                                  "connection", "data_error",
                                  "code_error"}


def test_same_signature_clusters_together():
    result = _classify()
    top = result.clusters[0]
    assert top.cause == "dependency_missing"
    assert set(top.tasks) == {"dwd_orders", "dws_orders_daily"}
    # the upstream-wait failure has a different signature -> own cluster
    assert any(c.tasks == ["ads_board_kpi"] for c in result.clusters)


def test_retry_verdicts():
    result = _classify()
    by_task = {c.tasks[0]: c for c in result.clusters}
    assert by_task["dim_users_sync"].retry_verdict == "transient"
    assert by_task["dwd_orders"].retry_verdict == "futile"
    assert by_task["rpt_weekly_mail"].retry_verdict == "untried"


def test_csv_input():
    csv = ("task,error,retries,final_status\n"
           "t1,OutOfMemoryError heap,1,failed\n"
           "t2,connect timeout to host,0,failed\n")
    result = _classify(csv)
    assert result.causes.get("resource") == 1
    # 'connect timeout' matches the timeout class before connection
    assert result.total == 2


def test_unknown_error_is_other():
    result = _classify('[{"task": "t", "error": "weird thing happened"}]')
    assert result.causes == {"other": 1}


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_failures("  ")
    with pytest.raises(ValueError):
        parse_failures('[{"error": "no task"}]')
    with pytest.raises(ValueError):
        parse_failures("error\nboom\n")


def test_report_both_langs():
    result = _classify()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "任务失败归因" in zh and "依赖缺失" in zh
    assert "Task Failure Attribution" in en and "futile" in en
    assert "rerun-plan" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.task_failure import api as tf_api

    app = FastAPI()
    app.include_router(tf_api.router)
    return TestClient(app)


def test_api_classify_inline():
    res = _client().post("/api/taskfailure/classify",
                         json={"export_text": EXPORT, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["total"] == 7
    assert "Task Failure Attribution" in body["report"]


def test_api_bad_export_400():
    res = _client().post("/api/taskfailure/classify",
                         json={"export_text": '[{"error": "x"}]'})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("TASKFAILURE_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/taskfailure/classify",
                         json={"export_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/taskfailure/classify",
                         json={"export_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.task_failure import advisor_llm

    monkeypatch.setattr(advisor_llm, "failure_note",
                        lambda result, lang="zh": "FAIL-NOTE")
    res = _client().post("/api/taskfailure/classify",
                         json={"export_text": EXPORT, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["failure_note"] == "FAIL-NOTE"


def test_api_health():
    body = _client().get("/api/taskfailure/health").json()
    assert body == {"status": "ok", "agent": "task_failure"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_taskfailure_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["taskfailure", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "任务失败归因" in res.output and "dwd_orders" in res.output


def test_cli_json_format():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["taskfailure", "-f", str(DEMO),
                                   "--format", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["total"] == 7


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "task_failure" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.task_failure.tools import task_failure

    out = task_failure(EXPORT, lang="en")
    assert "Task Failure Attribution" in out and "transient" in out
    assert "must not be empty" in task_failure("  ")
    assert "bad input" in task_failure('[{"error": "x"}]')


# ── history ledger + trend ───────────────────────────────────────────

def test_cli_history_and_trend(tmp_path):
    import json as _json

    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    ledger = tmp_path / "fail.jsonl"
    ledger.write_text(
        _json.dumps({"total": 3}) + "\n"
        + _json.dumps({"total": 5}) + "\n", encoding="utf-8")
    res = CliRunner().invoke(cli, [
        "taskfailure", "-f", str(DEMO), "--history", str(ledger),
        "--trend", "3", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "failures rising" in res.output
    lines = [_json.loads(x) for x in
             ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines[-1]["total"] == 7
    assert lines[-1]["cause_dependency_missing"] == 3
    ledger2 = tmp_path / "fail2.jsonl"
    ledger2.write_text(
        _json.dumps({"total": 3}) + "\n"
        + _json.dumps({"total": 5}) + "\n", encoding="utf-8")
    gate = CliRunner().invoke(cli, [
        "taskfailure", "-f", str(DEMO), "--history", str(ledger2),
        "--trend", "3", "--fail-on-trend"])
    assert gate.exit_code == 1
    missing = CliRunner().invoke(cli, ["taskfailure", "-f", str(DEMO),
                                       "--trend", "3"])
    assert missing.exit_code == 2
