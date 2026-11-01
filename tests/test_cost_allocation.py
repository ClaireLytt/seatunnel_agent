"""Tests for the cost_allocation agent (allocator / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.cost_allocation import (
    allocate_costs,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "costalloc_demo" / "usage.csv"


def _demo_bill(**kw):
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return allocate_costs(headers, rows, **kw)


# --------------------------------------------------------------- allocator

def test_demo_bill_numbers():
    bill = _demo_bill()
    assert bill.total == pytest.approx(304.8)
    by = {o.owner: o for o in bill.owners}
    assert by["trade"].total == pytest.approx(124.7)
    assert by["trade"].top_items[0] == ("dwd.orders", pytest.approx(77.0))
    assert by["(unallocated)"].items == 2
    assert bill.unallocated_share == pytest.approx(50 / 304.8)
    assert bill.owners[0].owner == "trade"      # biggest first


def test_findings_unallocated_and_concentration():
    bill = _demo_bill()
    codes = {(f.code, f.owner, f.severity) for f in bill.findings}
    assert ("CA001", "(unallocated)", "medium") in codes
    # trade holds 41% < 50% -> no CA002
    assert all(f.code != "CA002" for f in bill.findings)
    headers, rows = parse_rows("owner,item,storage_gb,compute_hours\n"
                               "big,t1,1000,0\nsmall,t2,10,0\n")
    bill2 = allocate_costs(headers, rows)
    assert any(f.code == "CA002" and f.owner == "big"
               for f in bill2.findings)


def test_unallocated_high_grade():
    headers, rows = parse_rows("owner,item,storage_gb,compute_hours\n"
                               ",tmp,1000,0\nteam,t,100,0\n")
    bill = allocate_costs(headers, rows)
    (f,) = [f for f in bill.findings if f.code == "CA001"]
    assert f.severity == "high"                 # ~91% unowned


def test_deterministic():
    assert _demo_bill().to_dict() == _demo_bill().to_dict()


def test_bad_inputs():
    headers, rows = parse_rows("owner,item\nt,x\n")
    with pytest.raises(ValueError, match="missing"):
        allocate_costs(headers, rows)
    h2, r2 = parse_rows("owner,item,storage_gb,compute_hours\nt,x,-1,0\n")
    with pytest.raises(ValueError, match="negative"):
        allocate_costs(h2, r2)
    h3, r3 = parse_rows(DEMO.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="prices"):
        allocate_costs(h3, r3, storage_price=-1)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    bill = _demo_bill()
    zh = render_markdown(bill, lang="zh")
    en = render_markdown(bill, lang="en")
    assert "成本分摊" in zh and "（无主）" in zh
    assert "Cost Allocation" in en and "CA001" in en
    headers, rows = parse_rows("owner,item,storage_gb,compute_hours\n"
                               "a,t1,10,0\nb,t2,10,0\nc,t3,10,0\n")
    clean = render_markdown(allocate_costs(headers, rows), lang="en")
    assert "Every cost has an owner" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["costalloc", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "成本分摊" in res.output
    res = runner.invoke(cli, ["costalloc", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"total": 304.8' in res.output
    res = runner.invoke(cli, ["costalloc", "--text",
                              "owner,item,storage_gb,compute_hours\n"
                              ",tmp,1000,0\nteam,t,100,0",
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["costalloc", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 0                   # demo tops out at medium


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.cost_allocation.tools import (
        cost_allocation,
    )

    out = cost_allocation(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "Cost Allocation" in out and "tmp.old_backup" in out
    assert "must not be empty" in cost_allocation("  ")
    assert "bad input" in cost_allocation("owner,item\nt,x\n")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.cost_allocation.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_allocate_and_health():
    client = _client()
    assert client.get("/api/costalloc/health").status_code == 200
    resp = client.post("/api/costalloc/allocate", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["total"] == 304.8
    assert "Cost Allocation" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/costalloc/allocate",
                       json={"data_text": "owner,item\nt,x\n"})
    assert resp.status_code == 400
