"""Tests for the grant-review agent (47): reviewer, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.grant_review import (
    parse_applications,
    render_markdown,
    review_grants,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "grantreview_demo" / "applications.json"
APPS = DEMO.read_text("utf-8")


def _review(text: str = APPS):
    return review_grants(parse_applications(text))


# ── reviewer ─────────────────────────────────────────────────────────

def test_demo_decisions():
    result = _review()
    by_name = {r.applicant: r for r in result.reviews}
    assert by_name["zhang3"].decision == "approve"
    assert by_name["wang5"].decision == "downgrade"
    assert by_name["li4"].decision == "reject"
    assert result.reviews[0].applicant == "li4"       # riskiest first


def test_s3_columns_detected():
    result = _review()
    wang = next(r for r in result.reviews if r.applicant == "wang5")
    assert set(wang.s3_columns) == {"dwd.users.phone", "dwd.users.id_card"}
    assert "mask_s3" in wang.downgrades


def test_wildcard_and_write_for_role():
    result = _review()
    li = next(r for r in result.reviews if r.applicant == "li4")
    assert "whole_table:dwd.users" in li.reasons
    assert "write_for_role:analyst" in li.reasons
    assert "duration:permanent" in li.reasons
    assert "thin_purpose" in li.reasons


def test_write_role_allowed_with_small_penalty():
    app = json.dumps({"applicant": "etl1", "role": "etl",
                      "purpose": "每日同步订单明细到数仓",
                      "tables": [{"table": "dwd.orders",
                                  "columns": ["order_id"]}],
                      "duration_days": 30, "write": True})
    r = _review(app).reviews[0]
    assert r.decision == "approve"
    assert "write_access" in r.reasons


def test_approve_has_no_downgrades():
    result = _review()
    zhang = next(r for r in result.reviews if r.applicant == "zhang3")
    assert zhang.downgrades == []


def test_single_object_accepted():
    app = json.dumps({"applicant": "a", "role": "analyst",
                      "purpose": "正常业务分析用途说明",
                      "tables": [{"table": "t", "columns": ["v"]}],
                      "duration_days": 30})
    assert _review(app).reviews[0].decision == "approve"


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_applications("   ")
    with pytest.raises(ValueError):
        parse_applications("not json")
    with pytest.raises(ValueError):
        parse_applications('{"applicant": "a"}')      # no tables
    with pytest.raises(ValueError):
        parse_applications('{"tables": [{"table": "t"}]}')


def test_report_both_langs():
    result = _review()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "权限申请审核" in zh and "降级批准" in zh
    assert "Permission Application Review" in en and "reject" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.grant_review import api as gr_api

    app = FastAPI()
    app.include_router(gr_api.router)
    return TestClient(app)


def test_api_review_inline():
    res = _client().post("/api/grantreview/review",
                         json={"application_text": APPS, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["reviews"]) == 3
    assert "Permission Application Review" in body["report"]


def test_api_bad_application_400():
    res = _client().post("/api/grantreview/review",
                         json={"application_text": "not json"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("GRANTREVIEW_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/grantreview/review",
                         json={"application_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/grantreview/review",
                         json={"application_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.grant_review import advisor_llm

    monkeypatch.setattr(advisor_llm, "review_note",
                        lambda result, lang="zh": "- a — ok")
    res = _client().post("/api/grantreview/review",
                         json={"application_text": APPS, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["replies"] == "- a — ok"


def test_api_health():
    body = _client().get("/api/grantreview/health").json()
    assert body == {"status": "ok", "agent": "grant_review"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_grantreview_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "grantreview", "-f", str(DEMO), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "权限申请审核" in res.output and "li4" in res.output


def test_cli_fail_on_reject_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["grantreview", "-f", str(DEMO),
                                   "--fail-on-reject"])
    assert res.exit_code == 1
    clean_app = json.dumps({"applicant": "a", "role": "analyst",
                            "purpose": "正常业务分析用途说明",
                            "tables": [{"table": "t", "columns": ["v"]}],
                            "duration_days": 30})
    clean = CliRunner().invoke(cli, ["grantreview", "--text", clean_app,
                                     "--fail-on-reject"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "grant_review" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.grant_review.tools import grant_review

    out = grant_review(APPS, lang="en")
    assert "Permission Application Review" in out and "li4" in out
    assert "must not be empty" in grant_review("  ")
    assert "bad input" in grant_review("not json")
