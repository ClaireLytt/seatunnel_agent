"""Tests for the mock_data agent (generator / report / CLI / tool / API)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.mock_data import (
    generate_mock,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "mockdata_demo" / "sample.csv"


def _demo():
    return parse_rows(DEMO.read_text(encoding="utf-8"))


# --------------------------------------------------------------- generator

def test_deterministic_same_seed():
    headers, rows = _demo()
    a = generate_mock(headers, rows, count=20, seed=7)
    b = generate_mock(headers, rows, count=20, seed=7)
    assert a.to_csv() == b.to_csv()
    c = generate_mock(headers, rows, count=20, seed=8)
    assert a.to_csv() != c.to_csv()


def test_sensitive_columns_never_sample_real_values():
    headers, rows = _demo()
    result = generate_mock(headers, rows, count=50, seed=1)
    for col in ("mobile", "id_card", "email", "user_name"):
        real = {r[col] for r in rows}
        got = {r[col] for r in result.rows if r[col]}
        assert not real & got, col
    phones = [r["mobile"] for r in result.rows if r["mobile"]]
    assert all(re.fullmatch(r"1[3-9]\d{9}", p) for p in phones)


def test_strategies_match_shapes():
    headers, rows = _demo()
    plans = {p.name: p for p in
             generate_mock(headers, rows, count=5).plans}
    assert plans["user_id"].strategy == "sequence"
    assert plans["mobile"].strategy == "fake_phone"
    assert plans["city"].strategy == "enum"


def test_ranges_dates_and_nulls_carry_over():
    csv = ("qty,price,dt,note\n"
           "10,1.50,2026-01-01,\n"
           "20,2.75,2026-01-05,x\n"
           "30,9.99,2026-01-31,\n"
           "40,5.00,2026-01-15,\n"
           "11,1.99,2026-01-10,\n"
           "22,3.33,2026-01-20,y\n"
           "33,7.77,2026-01-25,\n"
           "44,8.88,2026-01-28,z\n"
           "15,2.22,2026-01-02,\n"
           "26,6.66,2026-01-08,w\n"
           "37,4.44,2026-01-12,\n"
           "48,5.55,2026-01-18,v\n"
           "19,3.21,2026-01-22,\n")
    headers, rows = parse_rows(csv)
    result = generate_mock(headers, rows, count=200, seed=3)
    plans = {p.name: p for p in result.plans}
    assert plans["price"].strategy == "float_range"
    assert plans["dt"].strategy == "date_range"
    for r in result.rows:
        if r["price"] is not None:
            assert 1.50 <= float(r["price"]) <= 9.99
        if r["dt"] is not None:
            assert "2026-01-01" <= r["dt"] <= "2026-01-31"
    null_share = sum(1 for r in result.rows if r["note"] is None) / 200
    assert 0.3 <= null_share <= 0.85          # sample is ~54% null


def test_csv_roundtrip_parses():
    headers, rows = _demo()
    result = generate_mock(headers, rows, count=10, seed=5)
    h2, rows2 = parse_rows(result.to_csv())
    assert h2 == headers and len(rows2) == 10


def test_bad_inputs():
    headers, rows = _demo()
    with pytest.raises(ValueError, match="no columns"):
        generate_mock([], [])
    with pytest.raises(ValueError, match="no rows"):
        generate_mock(headers, [])
    with pytest.raises(ValueError, match="count"):
        generate_mock(headers, rows, count=0)


# ------------------------------------------------------------------ report

def test_report_both_langs():
    headers, rows = _demo()
    result = generate_mock(headers, rows, count=5)
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "测试数据生成" in zh and "合成" in zh
    assert "Mock Data" in en and "synthesized phone" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_csv_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["mockdata", "-f", str(DEMO), "-n", "5"])
    assert res.exit_code == 0, res.output
    assert "测试数据生成" in res.output
    out = tmp_path / "mock.csv"
    res = runner.invoke(cli, ["mockdata", "-f", str(DEMO), "-n", "7",
                              "--csv-out", str(out), "--format", "json"])
    assert res.exit_code == 0 and '"rows_generated": 7' in res.output
    assert out.read_text(encoding="utf-8").startswith("user_id,")


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["mockdata", "--text", "   "])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.mock_data.tools import mock_data

    out = mock_data(DEMO.read_text(encoding="utf-8"), count=5, lang="en")
    assert "Mock Data" in out and "sequence" in out
    assert "must not be empty" in mock_data("  ")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.mock_data.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_and_health():
    client = _client()
    assert client.get("/api/mockdata/health").status_code == 200
    resp = client.post("/api/mockdata/generate",
                       json={"data_text": DEMO.read_text(encoding="utf-8"),
                             "count": 5, "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["rows_generated"] == 5
    assert body["result"]["csv"].startswith("user_id,")
    assert "Mock Data" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/mockdata/generate", json={"data_text": "  "})
    assert resp.status_code == 400
