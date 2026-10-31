"""Tests for the contract_gen agent (generator / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.contract_gen import (
    generate_contract,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "contractgen_demo" / "tables.sql"

DDL = """
CREATE TABLE ods.user_info (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名',
  amount    DECIMAL(16,2) COMMENT '累计消费'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE stg.raw_events (
  event_id BIGINT,
  user_id  BIGINT,
  event_ts TIMESTAMP COMMENT '事件时间'
) STORED AS ORC;
"""


# ---------------------------------------------------------------- generator

def test_generate_basic_shape():
    draft = generate_contract(DDL)
    assert [t.name for t in draft.tables] == ["ods.user_info",
                                              "stg.raw_events"]
    assert draft.columns_total == 6             # data columns only
    ui = draft.tables[0]
    assert ui.require_comments is True          # 100% coverage
    assert ui.partitioned_by == ["dt"]
    assert ui.columns[2]["type"] == "decimal(16, 2)"
    assert ui.columns[2]["comment"] is True     # commented columns pinned


def test_partition_columns_declared_too():
    # declared alongside data columns so require_comments round-trips
    draft = generate_contract(DDL)
    names = [c["name"] for c in draft.tables[0].columns]
    assert "dt" in names


def test_low_coverage_pins_existing_comments_only():
    draft = generate_contract(DDL)
    raw = draft.tables[1]
    assert raw.require_comments is False        # 1/3 coverage
    flagged = [c["name"] for c in raw.columns if c.get("comment")]
    assert flagged == ["event_ts"]
    assert raw.comment_coverage == pytest.approx(1 / 3)


def test_yaml_roundtrips_through_contract_check():
    from seatunnel_agent.agents.data.contract_check.checker import (
        check_sql_text,
    )

    draft = generate_contract(DDL)
    report = check_sql_text(DDL, contract=draft.yaml_text)
    assert report.tables_checked == 2
    assert report.findings == []                # draft promises hold as-is


def test_strict_and_no_types():
    draft = generate_contract(DDL, with_types=False, allow_extra=False)
    assert "type:" not in draft.yaml_text
    assert "allow_extra_columns: false" in draft.yaml_text


def test_table_filter_and_missing_table():
    draft = generate_contract(DDL, tables=["ODS.user_info"])
    assert [t.name for t in draft.tables] == ["ods.user_info"]
    with pytest.raises(ValueError, match="not in the DDL"):
        generate_contract(DDL, tables=["dwd.nope"])


def test_threshold_tunes_require_comments():
    draft = generate_contract(DDL, comment_threshold=0.3)
    assert draft.tables[1].require_comments is True


def test_empty_and_bad_inputs():
    with pytest.raises(ValueError, match="empty"):
        generate_contract("   ")
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        generate_contract("SELECT 1")
    with pytest.raises(ValueError, match="threshold"):
        generate_contract(DDL, comment_threshold=1.5)


def test_quote_handles_odd_names():
    from seatunnel_agent.agents.data.contract_gen.generator import _quote

    assert _quote("ods.user_info") == "ods.user_info"
    assert _quote("a b") == '"a b"'


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = generate_contract(DDL)
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "契约草稿" in zh and "```yaml" in zh
    assert "Contract Draft" in en and "require_comments" in en
    assert "ods.user_info" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_and_json():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["contractgen", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "契约草稿" in res.output
    res = runner.invoke(cli, ["contractgen", "-f", str(DEMO),
                              "--format", "json", "--strict"])
    assert res.exit_code == 0, res.output
    assert '"tables_total": 4' in res.output
    assert "allow_extra_columns: false" in res.output


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["contractgen", "--text", "SELECT 1"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.contract_gen.tools import contract_gen

    out = contract_gen(DDL, tables="stg.raw_events", strict=True, lang="en")
    assert "stg.raw_events" in out and "allow_extra_columns: false" in out
    assert "ods.user_info" not in out
    assert "must not be empty" in contract_gen("  ")
    assert "bad input" in contract_gen("SELECT 1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.contract_gen.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_and_health():
    client = _client()
    assert client.get("/api/contractgen/health").status_code == 200
    resp = client.post("/api/contractgen/generate",
                       json={"sql_text": DDL, "lang": "en",
                             "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["tables_total"] == 2
    assert "Contract Draft" in body["report"]


def test_api_bad_input_422_400():
    client = _client()
    resp = client.post("/api/contractgen/generate",
                       json={"sql_text": "SELECT 1"})
    assert resp.status_code == 400
