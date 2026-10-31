"""Tests for the join_audit agent (auditor / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.join_audit import (
    audit_join,
    parse_keys,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "joinaudit_demo"


def _demo_report():
    lh, lrows = parse_rows((DEMO / "orders.csv").read_text(encoding="utf-8"))
    rh, rrows = parse_rows(
        (DEMO / "user_tags.csv").read_text(encoding="utf-8"))
    return audit_join(lh, lrows, rh, rrows, parse_keys("user_id=uid"))


# -------------------------------------------------------------------- keys

def test_parse_keys_forms():
    assert parse_keys("k") == [("k", "k")]
    assert parse_keys("a=b") == [("a", "b")]
    assert parse_keys("a=b, c") == [("a", "b"), ("c", "c")]
    with pytest.raises(ValueError, match="join key"):
        parse_keys("  ")


# ----------------------------------------------------------------- auditor

def test_demo_metrics_and_codes():
    report = _demo_report()
    assert report.left_rows == 8 and report.right_rows == 6
    assert report.left_null_keys == 1
    assert report.joined_rows == 8          # 3*2 + 1 + 1
    assert report.left_match_rate == pytest.approx(5 / 7)
    assert report.right_match_rate == pytest.approx(4 / 6)
    assert {f.code for f in report.findings} == {"JA001", "JA002",
                                                 "JA003", "JA004"}


def test_ja001_needs_dups_on_both_sides():
    lh, lrows = parse_rows("k,v\n1,a\n1,b\n2,c\n")
    rh, rrows = parse_rows("k,w\n1,x\n2,y\n")
    report = audit_join(lh, lrows, rh, rrows, parse_keys("k"))
    assert all(f.code != "JA001" for f in report.findings)  # 1:N is fine
    assert report.explosion == pytest.approx(1.0)


def test_clean_one_to_one_join():
    lh, lrows = parse_rows("k,v\n1,a\n2,b\n")
    rh, rrows = parse_rows("k,w\n1,x\n2,y\n")
    report = audit_join(lh, lrows, rh, rrows, parse_keys("k"))
    assert report.findings == []
    assert report.left_match_rate == 1.0 and report.joined_rows == 2


def test_match_rate_grading():
    lh, lrows = parse_rows("k\n" + "\n".join(str(i) for i in range(10)))
    rh, rrows = parse_rows("k\n0\n1\n2\n3\n")
    report = audit_join(lh, lrows, rh, rrows, parse_keys("k"))
    (f,) = [f for f in report.findings if f.code == "JA002"]
    assert f.severity == "high"             # 40% < 50%


def test_multi_key_join():
    lh, lrows = parse_rows("a,b,v\n1,x,10\n2,y,20\n")
    rh, rrows = parse_rows("a,b,w\n1,x,ok\n2,z,no\n")
    report = audit_join(lh, lrows, rh, rrows, parse_keys("a,b"))
    assert report.left_match_rate == pytest.approx(0.5)


def test_bad_inputs():
    lh, lrows = parse_rows("k\n1\n")
    with pytest.raises(ValueError, match="no column 'x'"):
        audit_join(lh, lrows, lh, lrows, parse_keys("x"))
    with pytest.raises(ValueError, match="at least one row"):
        audit_join(lh, [], lh, lrows, parse_keys("k"))


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = _demo_report()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "关联质量审计" in zh and "JA001" in zh
    assert "Join Audit" in en and "many-to-many" in en
    lh, lrows = parse_rows("k\n1\n")
    clean = render_markdown(
        audit_join(lh, lrows, lh, lrows, parse_keys("k")), lang="en")
    assert "clean" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["joinaudit", "-l", str(DEMO / "orders.csv"),
            "-r", str(DEMO / "user_tags.csv"), "-k", "user_id=uid"]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "关联质量审计" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"joined_rows": 8' in res.output
    res = runner.invoke(cli, args + ["--fail-on-high"])
    assert res.exit_code == 1


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.join_audit.tools import join_audit

    left = (DEMO / "orders.csv").read_text(encoding="utf-8")
    right = (DEMO / "user_tags.csv").read_text(encoding="utf-8")
    out = join_audit(left, right, "user_id=uid", lang="en")
    assert "JA001" in out and "x1.6" in out
    assert "required" in join_audit("", right, "k")
    assert "bad input" in join_audit(left, right, "nope")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.join_audit.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_audit_and_health():
    client = _client()
    assert client.get("/api/joinaudit/health").status_code == 200
    resp = client.post("/api/joinaudit/audit", json={
        "left_text": (DEMO / "orders.csv").read_text(encoding="utf-8"),
        "right_text": (DEMO / "user_tags.csv").read_text(encoding="utf-8"),
        "keys": "user_id=uid", "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["joined_rows"] == 8
    assert "Join Audit" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/joinaudit/audit", json={
        "left_text": "k\n1\n", "right_text": "k\n1\n", "keys": "zz"})
    assert resp.status_code == 400
