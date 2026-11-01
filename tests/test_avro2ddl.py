"""Tests for the avro2ddl agent (converter / report / CLI / tool / API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.avro2ddl import (
    convert_schema,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "avro2ddl_demo" / "order.avsc"


def _schema() -> str:
    return DEMO.read_text(encoding="utf-8")


# --------------------------------------------------------------- converter

def test_hive_mapping():
    draft = convert_schema(_schema())
    assert draft.table == "shop.Order" and draft.flavor == "avro"
    by = {c.name: c for c in draft.columns}
    assert by["id"].ddl_type == "BIGINT" and by["id"].comment == "订单ID"
    assert by["amount"].ddl_type == "DECIMAL(16,2)"
    assert by["created"].ddl_type == "TIMESTAMP"
    assert by["tags"].ddl_type == "ARRAY<STRING>"
    assert by["note"].ddl_type == "STRING" and by["note"].nullable
    assert by["mixed"].ddl_type == "STRING"
    assert by["mixed"].note == "union_lossy"
    assert "[paid, refund]" in draft.ddl_text      # enum symbols kept
    assert draft.lossy == 2                        # enum + mixed union
    assert draft.ddl_text.endswith("STORED AS ORC;")


def test_doris_mapping_and_stub():
    draft = convert_schema(_schema(), dialect="doris")
    by = {c.name: c for c in draft.columns}
    assert by["created"].ddl_type == "DATETIME"
    assert by["tags"].ddl_type == "JSON"
    assert by["tags"].note == "complex_lossy"
    assert "DUPLICATE KEY (id)" in draft.ddl_text
    assert "BUCKETS 8" in draft.ddl_text


def test_ddl_round_trips_through_parser():
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    draft = convert_schema(_schema())
    parsed, _ = parse_schema_script(draft.ddl_text, "hive")
    schema = next(iter(parsed.values()))
    assert len(schema.columns) == 7


def test_json_schema_flavor():
    doc = json.dumps({
        "title": "events",
        "properties": {
            "id": {"type": "integer"},
            "price": {"type": "number"},
            "day": {"type": "string", "format": "date"},
            "at": {"type": "string", "format": "date-time"},
            "meta": {"type": "object"}}})
    draft = convert_schema(doc)
    by = {c.name: c for c in draft.columns}
    assert draft.flavor == "jsonschema" and draft.table == "events"
    assert by["id"].ddl_type == "BIGINT"
    assert by["day"].ddl_type == "DATE"
    assert by["at"].ddl_type == "TIMESTAMP"
    assert by["meta"].note == "complex_lossy"


def test_table_override_and_bad_inputs():
    draft = convert_schema(_schema(), table="ods.orders_raw")
    assert "CREATE TABLE ods.orders_raw (" in draft.ddl_text
    with pytest.raises(ValueError, match="not valid JSON"):
        convert_schema("{")
    with pytest.raises(ValueError, match="neither an Avro"):
        convert_schema(json.dumps({"x": 1}))
    with pytest.raises(ValueError, match="dialect"):
        convert_schema(_schema(), dialect="oracle")
    with pytest.raises(ValueError, match="no fields"):
        convert_schema(json.dumps({"type": "record", "name": "E",
                                   "fields": []}))


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = convert_schema(_schema())
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "消息 Schema 建表" in zh and "```sql" in zh
    assert "Avro to DDL" in en and "symbols kept" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_ddl_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["avro2ddl", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "消息 Schema 建表" in res.output
    out = tmp_path / "landing.sql"
    res = runner.invoke(cli, ["avro2ddl", "-f", str(DEMO),
                              "--dialect", "doris",
                              "--ddl-out", str(out), "--format", "json"])
    assert res.exit_code == 0 and '"lossy": 3' in res.output
    assert "DUPLICATE KEY" in out.read_text(encoding="utf-8")


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["avro2ddl", "--text", "{"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.avro2ddl.tools import avro2ddl

    out = avro2ddl(_schema(), dialect="doris", lang="en")
    assert "Avro to DDL" in out and "DUPLICATE KEY" in out
    assert "must not be empty" in avro2ddl("  ")
    assert "bad input" in avro2ddl("{")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.avro2ddl.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_convert_and_health():
    client = _client()
    assert client.get("/api/avro2ddl/health").status_code == 200
    resp = client.post("/api/avro2ddl/convert", json={
        "schema_text": _schema(), "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["columns_total"] == 7
    assert "Avro to DDL" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/avro2ddl/convert", json={"schema_text": "{"})
    assert resp.status_code == 400
