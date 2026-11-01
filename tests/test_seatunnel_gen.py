"""Tests for the seatunnel_gen agent (generator / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.seatunnel_gen import (
    generate_config,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "seatunnelgen_demo" / "products.sql"


def _ddl() -> str:
    return DEMO.read_text(encoding="utf-8")


# --------------------------------------------------------------- generator

def test_cdc_to_doris_draft():
    draft = generate_config(_ddl(), "mysql-cdc", "doris")
    assert draft.source == "MySQL-CDC" and draft.sink == "Doris"
    assert draft.job_mode == "STREAMING"       # CDC source → streaming
    assert draft.table == "inventory.products" and draft.columns == 4
    assert draft.lint_errors == 0
    assert '"database-name" = "inventory"' in draft.hocon_text
    assert 'table = "products"' in draft.hocon_text
    assert 'plugin_output = "products"' in draft.hocon_text


def test_filled_vs_placeholders():
    draft = generate_config(_ddl(), "MySQL-CDC", "Doris")
    assert "source.database-name" in draft.filled
    assert "sink.table" in draft.filled
    assert "source.hostname" in draft.placeholders
    assert "sink.password" in draft.placeholders


def test_batch_default_and_override():
    draft = generate_config(_ddl(), "Jdbc", "Hive")
    assert draft.job_mode == "BATCH"
    assert 'table_name = "inventory.products"' in draft.hocon_text
    draft = generate_config(_ddl(), "Jdbc", "Hive", job_mode="streaming")
    assert draft.job_mode == "STREAMING"


def test_kafka_topic_filled_from_table():
    draft = generate_config(_ddl(), "Kafka", "Console")
    assert 'topic = "products"' in draft.hocon_text
    assert "source.topic" in draft.filled


def test_draft_lints_clean_via_config_lint():
    from seatunnel_agent.agents.data.config_lint import lint_text

    draft = generate_config(_ddl(), "MySQL-CDC", "ClickHouse")
    result = lint_text(draft.hocon_text)
    assert result.ok, [f.to_dict() for f in result.findings]


def test_multi_table_warns_and_uses_first():
    ddl = _ddl() + "\nCREATE TABLE other.t2 (a INT);"
    draft = generate_config(ddl, "Jdbc", "Doris")
    assert draft.table == "inventory.products"
    assert any("2 tables" in w for w in draft.warnings)


def test_bad_inputs():
    with pytest.raises(ValueError, match="unknown source connector"):
        generate_config(_ddl(), "NopeDB", "Doris")
    with pytest.raises(ValueError, match="cannot be the source"):
        generate_config(_ddl(), "Doris", "Hive")   # Doris is sink-only
    with pytest.raises(ValueError, match="job_mode"):
        generate_config(_ddl(), "Jdbc", "Doris", job_mode="TURBO")
    with pytest.raises(ValueError, match="parallelism"):
        generate_config(_ddl(), "Jdbc", "Doris", parallelism=0)
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        generate_config("SELECT 1", "Jdbc", "Doris")


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = generate_config(_ddl(), "MySQL-CDC", "Doris")
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "作业草稿" in zh and "```hocon" in zh
    assert "SeaTunnel Job Draft" in en and "replace before running" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_conf_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["seatunnelgen", "-f", str(DEMO), "-s", "MySQL-CDC",
            "-k", "Doris"]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "作业草稿" in res.output
    out = tmp_path / "job.conf"
    res = runner.invoke(cli, args + ["--conf-out", str(out),
                                     "--format", "json"])
    assert res.exit_code == 0 and '"lint_errors": 0' in res.output
    assert out.read_text(encoding="utf-8").startswith("env {")


def test_cli_bad_connector():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["seatunnelgen", "-f", str(DEMO),
                                   "-s", "NopeDB", "-k", "Doris"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.seatunnel_gen.tools import (
        seatunnel_gen,
    )

    out = seatunnel_gen(_ddl(), "MySQL-CDC", "Doris", lang="en")
    assert "SeaTunnel Job Draft" in out and "STREAMING" in out
    assert "must not be empty" in seatunnel_gen("  ", "Jdbc", "Doris")
    assert "required" in seatunnel_gen(_ddl(), "", "Doris")
    assert "bad input" in seatunnel_gen(_ddl(), "NopeDB", "Doris")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.seatunnel_gen.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_and_health():
    client = _client()
    assert client.get("/api/seatunnelgen/health").status_code == 200
    resp = client.post("/api/seatunnelgen/generate", json={
        "sql_text": _ddl(), "source": "MySQL-CDC", "sink": "Doris",
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["job_mode"] == "STREAMING"
    assert body["result"]["lint_errors"] == 0
    assert "SeaTunnel Job Draft" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/seatunnelgen/generate", json={
        "sql_text": _ddl(), "source": "NopeDB", "sink": "Doris"})
    assert resp.status_code == 400
