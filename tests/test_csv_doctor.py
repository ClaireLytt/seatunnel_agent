"""Tests for the csv_doctor agent (doctor / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.csv_doctor import (
    diagnose_csv,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "csvdoctor_demo" / "broken.csv"


def _demo_report():
    return diagnose_csv(DEMO.read_text(encoding="utf-8"))


def _codes(report):
    return {f.code for f in report.findings}


# ------------------------------------------------------------------ doctor

def test_demo_diagnosis_and_repair():
    report = _demo_report()
    assert report.delimiter == ";"
    assert report.rows == 4 and report.columns == 4
    assert _codes(report) == {"CD001", "CD002", "CD005", "CD006", "CD007"}
    lines = report.fixed_csv.splitlines()
    assert lines[0] == "id,name,amount,name_2"      # dupe suffixed
    assert "订单一" in lines[1]                      # mojibake recovered
    assert lines[2].endswith("20,")                  # short row padded
    assert "y;extra" in lines[3]                     # overflow merged
    assert "\x01" not in report.fixed_csv            # control stripped


def test_mojibake_before_after_sample():
    report = _demo_report()
    (f,) = [f for f in report.findings if f.code == "CD005"]
    assert f.count == 2 and "订单一" in f.sample and "->" in f.sample


def test_replacement_chars_graded_high():
    report = diagnose_csv("a,b\n1,x�y\n")
    (f,) = [f for f in report.findings if f.code == "CD004"]
    assert f.severity == "high" and f.count == 1


def test_ragged_share_grades_high():
    rows = "\n".join(f"{i},x" if i % 2 else f"{i}" for i in range(1, 11))
    report = diagnose_csv("a,b\n" + rows)
    (f,) = [f for f in report.findings if f.code == "CD002"]
    assert f.severity == "high"                      # 50% ragged


def test_unbalanced_quotes_reported():
    report = diagnose_csv('a,b\n1,"broken\n2,ok\n')
    assert any(f.code == "CD003" for f in report.findings)


def test_clean_file_and_tab_delimiter():
    report = diagnose_csv("a\tb\n1\t2\n3\t4\n")
    assert report.clean and report.delimiter == "\t"
    assert report.fixed_csv.splitlines()[0] == "a,b"


def test_fixed_csv_round_trips():
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    headers, rows = parse_rows(_demo_report().fixed_csv)
    assert headers == ["id", "name", "amount", "name_2"]
    assert len(rows) == 4


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty"):
        diagnose_csv("   ")
    with pytest.raises(ValueError, match="header line"):
        diagnose_csv("only_one_line")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = _demo_report()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "CSV 急救" in zh and "订单一" in zh
    assert "CSV Doctor" in en and "```csv" in en
    clean = render_markdown(diagnose_csv("a,b\n1,2\n"), lang="en")
    assert "nothing to repair" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_gate_and_csv_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["csvdoctor", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "CSV 急救" in res.output
    out = tmp_path / "fixed.csv"
    res = runner.invoke(cli, ["csvdoctor", "-f", str(DEMO),
                              "--csv-out", str(out), "--format", "json"])
    assert res.exit_code == 0 and '"clean": false' in res.output
    assert out.read_text(encoding="utf-8").startswith("id,name,amount")
    res = runner.invoke(cli, ["csvdoctor", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1                        # CD002 high
    res = runner.invoke(cli, ["csvdoctor", "--text", "a,b\n1,2",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.csv_doctor.tools import csv_doctor

    out = csv_doctor(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "CSV Doctor" in out and "CD005" in out
    assert "must not be empty" in csv_doctor("  ")
    assert "bad input" in csv_doctor("one_line")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.csv_doctor.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_diagnose_and_health():
    client = _client()
    assert client.get("/api/csvdoctor/health").status_code == 200
    resp = client.post("/api/csvdoctor/diagnose", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["clean"] is False
    assert body["result"]["fixed_csv"].startswith("id,name,amount")
    assert "CSV Doctor" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/csvdoctor/diagnose",
                       json={"data_text": "one_line"})
    assert resp.status_code == 400
