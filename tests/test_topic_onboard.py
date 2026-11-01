"""Tests for the topic_onboard chain (core / report / CLI / tool)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.avro2ddl import (
    onboard_topic,
    render_onboard,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "avro2ddl_demo" / "order.avsc"

SAMPLE = "id,amount\n1,9.5\n2,7.0\n"


def _bundle(**kw):
    return onboard_topic(DEMO.read_text(encoding="utf-8"), **kw)


# -------------------------------------------------------------------- core

def test_bundle_carries_all_three_artifacts():
    b = _bundle()
    assert b.table == "shop.Order" and b.columns_total == 7
    assert "CREATE TABLE shop.Order" in b.ddl_text
    assert "source {" in b.hocon_text and b.placeholders
    assert "shop.order" in b.contract_yaml      # contract normalizes case
    assert b.rules_yaml == "" and b.rules_total == 0


def test_sample_adds_rules_yaml():
    b = _bundle(sample_text=SAMPLE)
    assert b.rules_total > 0
    assert "row_count" in b.rules_yaml


def test_dialect_and_connectors_pass_through():
    b = _bundle(dialect="doris", source="kafka", sink="doris")
    assert "DUPLICATE KEY" in b.ddl_text
    assert b.sink == "doris"


def test_bad_schema_raises():
    with pytest.raises(ValueError):
        onboard_topic("{")


# ------------------------------------------------------------------ report

def test_report_sections_and_no_sample_hint():
    zh = render_onboard(_bundle(), lang="zh")
    assert "Topic 接入套件" in zh and "```hocon" in zh
    assert "未提供样例数据" in zh
    en = render_onboard(_bundle(sample_text=SAMPLE), lang="en")
    assert "Topic Onboarding Kit" in en
    assert "4. DQC rules" in en and "No sample rows" not in en


# --------------------------------------------------------------------- CLI

def test_cli_out_dir_writes_kit(tmp_path):
    from seatunnel_agent.cli import cli

    sample = tmp_path / "sample.csv"
    sample.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "kit"
    res = CliRunner().invoke(cli, [
        "topiconboard", "-f", str(DEMO), "--sample", str(sample),
        "--out-dir", str(out), "--format", "json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["columns_total"] == 7 and payload["rules_total"] > 0
    assert (out / "ddl.sql").exists() and (out / "job.conf").exists()
    assert (out / "contract.yaml").exists()
    assert "row_count" in (out / "rules.yaml").read_text(encoding="utf-8")


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["topiconboard", "--text", "{"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.avro2ddl.tools import topic_onboard

    out = topic_onboard(DEMO.read_text(encoding="utf-8"), sample=SAMPLE,
                        lang="en")
    assert "Topic Onboarding Kit" in out and "```yaml" in out
    assert "must not be empty" in topic_onboard("  ")
    assert "bad input" in topic_onboard("{")
