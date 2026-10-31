"""Tests for the retention_policy agent (advisor / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.retention_policy import (
    advise_retention,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "retention_demo" / "partitions.csv"


def _demo_report(**kw):
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return advise_retention(headers, rows, **kw)


# ----------------------------------------------------------------- advisor

def test_today_is_data_max_and_reproducible():
    a, b = _demo_report(), _demo_report()
    assert a.today == "2026-10-30"
    assert a.to_dict() == b.to_dict()


def test_ttl_from_oldest_warm_partition():
    report = _demo_report()
    by = {t.table: t for t in report.tables}
    # dwd.orders: oldest still-read partition is 76d old -> +30 grace,
    # rounded up to 30-day steps = 120
    assert by["dwd.orders"].ttl_days == 120
    # ods.click_log: only today's partition is warm -> minimum 30
    assert by["ods.click_log"].ttl_days == 30
    assert by["dim.users"].ttl_days == 60


def test_archive_and_purge_candidates():
    by = {t.table: t for t in _demo_report().tables}
    orders = by["dwd.orders"]
    assert orders.archive == ["dt=2025-11-20", "dt=2026-01-05",
                              "dt=2026-04-10"]
    # dt=2026-04-10 WAS read once (2026-05-01) — archive, not purge
    assert orders.purge == ["dt=2025-11-20", "dt=2026-01-05"]
    assert by["dim.users"].archive == []


def test_findings_graded_and_order():
    report = _demo_report()
    codes = {(f.code, f.table, f.severity) for f in report.findings}
    assert ("RP001", "ods.click_log", "high") in codes      # 74% cold
    assert ("RP001", "dwd.orders", "medium") in codes       # 47% cold
    assert ("RP002", "dwd.orders", "medium") in codes
    assert report.tables[0].table == "ods.click_log"        # coldest first
    assert report.reclaimable_gb == pytest.approx(256.2)


def test_unparseable_partition_skipped_with_rp003():
    csv = ("table,partition,size_gb,last_access\n"
           "t,dt=2026-10-01,1,2026-10-02\n"
           "t,region=cn,5,\n")
    headers, rows = parse_rows(csv)
    report = advise_retention(headers, rows)
    assert report.skipped == ["t/region=cn"]
    assert any(f.code == "RP003" for f in report.findings)


def test_bad_inputs():
    headers, rows = parse_rows("table,partition\nt,dt=2026-01-01\n")
    with pytest.raises(ValueError, match="missing"):
        advise_retention(headers, rows)
    h2, r2 = parse_rows("table,partition,size_gb,last_access\n"
                        "t,region=cn,1,\n")
    with pytest.raises(ValueError, match="parseable date"):
        advise_retention(h2, r2)
    h3, r3 = parse_rows(DEMO.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="active_days"):
        advise_retention(h3, r3, active_days=0)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = _demo_report()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "生命周期建议" in zh and "RP001" in zh
    assert "Retention Advice" in en and "reclaimable" in en
    headers, rows = parse_rows("table,partition,size_gb,last_access\n"
                               "t,dt=2026-10-01,1,2026-10-01\n")
    clean = render_markdown(advise_retention(headers, rows), lang="en")
    assert "inside its keep window" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["retention", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "生命周期建议" in res.output
    res = runner.invoke(cli, ["retention", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"reclaimable_gb": 256.2' in res.output
    res = runner.invoke(cli, ["retention", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["retention", "--text",
                              "table,partition,size_gb,last_access\n"
                              "t,dt=2026-10-01,1,2026-10-01",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.retention_policy.tools import (
        retention_policy,
    )

    out = retention_policy(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "RP001" in out and "ods.click_log" in out
    assert "must not be empty" in retention_policy("  ")
    assert "bad input" in retention_policy("table,partition\nt,p\n")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.retention_policy.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_advise_and_health():
    client = _client()
    assert client.get("/api/retention/health").status_code == 200
    resp = client.post("/api/retention/advise", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["reclaimable_gb"] == 256.2
    assert "Retention Advice" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/retention/advise", json={
        "data_text": "table,partition\nt,p\n"})
    assert resp.status_code == 400
