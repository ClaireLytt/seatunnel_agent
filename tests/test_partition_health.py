"""Tests for the partition-health agent (56): analyzer, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.partition_health import (
    analyze_partitions,
    parse_partition_listing,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "partitionhealth_demo" / "partitions.csv"
CSV = DEMO.read_text("utf-8")


def _check(text: str = CSV):
    return analyze_partitions(parse_partition_listing(text))


# ── analyzer ─────────────────────────────────────────────────────────

def test_demo_findings():
    result = _check()
    assert result.tables == 3 and result.partitions == 11
    codes = {(f.code, f.table) for f in result.findings}
    assert ("PH001", "ods.click_log") in codes      # 10-27/28 missing
    assert ("PH002", "dwd.orders") in codes         # 10-28 empty
    assert ("PH003", "dwd.orders") in codes         # 95 GB vs 8 GB median
    assert ("PH004", "dwd.orders") in codes         # latest surged
    assert ("PH005", "ods.click_log") in codes      # latest shrank
    # non-dated dim.users triggers nothing
    assert not any(f.table == "dim.users" for f in result.findings)


def test_gap_evidence():
    f = next(f for f in _check().findings if f.code == "PH001")
    assert f.detail["gaps"] == ["2026-10-27 (+2)"]
    assert f.severity == "high"


def test_surge_ratio_and_grading():
    f = next(f for f in _check().findings if f.code == "PH004")
    assert f.detail["ratio"] == 11.7 and f.severity == "high"


def test_shrink_detected():
    f = next(f for f in _check().findings if f.code == "PH005")
    assert f.detail["size_gb"] == 6.0 and f.severity == "mid"


def test_healthy_listing_clean():
    rows = "table,partition,size_gb,rows\n" + "\n".join(
        f"t,dt=2026-10-{d:02d},10.{d % 3},1000" for d in range(20, 28))
    result = _check(rows)
    assert result.findings == []
    assert "healthy" in render_markdown(result, lang="en")


def test_skew_needs_enough_partitions():
    rows = ("table,partition,size_gb\n"
            "t,dt=2026-10-01,1\n"
            "t,dt=2026-10-02,100\n")
    codes = {f.code for f in _check(rows).findings}
    assert "PH003" not in codes            # under 4 sized partitions


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_partition_listing("  ")
    with pytest.raises(ValueError):
        parse_partition_listing('[{"partition": "dt=1"}]')
    with pytest.raises(ValueError):
        parse_partition_listing('[{"table": "t"}]')


def test_report_both_langs():
    result = _check()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "分区健康体检" in zh and "日期断档" in zh
    assert "Partition Health" in en and "backfill" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.partition_health import api as ph_api

    app = FastAPI()
    app.include_router(ph_api.router)
    return TestClient(app)


def test_api_check_inline():
    res = _client().post("/api/partitionhealth/check",
                         json={"listing_text": CSV, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["tables"] == 3
    assert "Partition Health" in body["report"]


def test_api_bad_listing_400():
    res = _client().post("/api/partitionhealth/check",
                         json={"listing_text": '[{"partition": "x"}]'})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("PARTITIONHEALTH_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/partitionhealth/check",
                         json={"listing_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/partitionhealth/check",
                         json={"listing_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.partition_health import advisor_llm

    monkeypatch.setattr(advisor_llm, "partition_note",
                        lambda result, lang="zh": "PART-NOTE")
    res = _client().post("/api/partitionhealth/check",
                         json={"listing_text": CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["partition_note"] == "PART-NOTE"


def test_api_health():
    body = _client().get("/api/partitionhealth/health").json()
    assert body == {"status": "ok", "agent": "partition_health"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_partitionhealth_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["partitionhealth", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "分区健康体检" in res.output and "PH001" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["partitionhealth", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "partitionhealth", "--text",
        "table,partition,size_gb\nt,dt=2026-10-01,10\nt,dt=2026-10-02,11",
        "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "partition_health" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.partition_health.tools import (
        partition_health,
    )

    out = partition_health(CSV, lang="en")
    assert "Partition Health" in out and "PH004" in out
    assert "must not be empty" in partition_health("  ")
    assert "bad input" in partition_health('[{"partition": "x"}]')
