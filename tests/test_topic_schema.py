"""Tests for the topic_schema agent (differ / report / CLI / tool / API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.topic_schema import (
    diff_topic_schemas,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "topicschema_demo"


def _demo(mode="backward"):
    return diff_topic_schemas(
        (DEMO / "old.json").read_text(encoding="utf-8"),
        (DEMO / "new.json").read_text(encoding="utf-8"), mode=mode)


def _avro(fields) -> str:
    return json.dumps({"type": "record", "name": "T", "fields": fields})


# ------------------------------------------------------------------ differ

def test_demo_backward_verdict():
    report = _demo()
    assert report.flavor == "avro" and not report.compatible
    by = {(f.kind, f.fld): f for f in report.findings}
    assert by[("field_added", "status")].severity == "breaking"
    assert by[("field_removed", "legacy")].severity == "risk"
    assert by[("field_added", "tag")].severity == "info"      # nullable
    assert by[("field_removed", "note")].severity == "info"   # had default
    assert by[("type_changed", "amount")].severity == "info"  # promotion


def test_forward_and_full_modes():
    fwd = _demo(mode="forward")
    by = {(f.kind, f.fld): f.severity for f in fwd.findings}
    assert by[("field_removed", "legacy")] == "breaking"
    assert by[("field_added", "status")] == "risk"
    full = _demo(mode="full")
    assert not full.compatible
    by_full = {(f.kind, f.fld): f.severity for f in full.findings}
    assert by_full[("field_added", "status")] == "breaking"
    assert by_full[("field_removed", "legacy")] == "breaking"


def test_type_rules():
    old = _avro([{"name": "a", "type": "int"},
                 {"name": "b", "type": "string"}])
    new = _avro([{"name": "a", "type": "string"},
                 {"name": "b", "type": ["null", "string"]}])
    report = diff_topic_schemas(old, new, mode="full")
    by = {f.fld: f for f in report.findings}
    assert by["a"].severity == "breaking"       # int -> string
    assert by["b"].severity == "info"           # widened by null only
    assert by["b"].kind == "type_changed"


def test_json_schema_flavor_and_requirement():
    old = json.dumps({"properties": {"id": {"type": "integer"},
                                     "note": {"type": "string"}},
                      "required": ["id"]})
    new = json.dumps({"properties": {"id": {"type": "integer"},
                                     "note": {"type": "string"},
                                     "tag": {"type": "string"}},
                      "required": ["id", "note"]})
    report = diff_topic_schemas(old, new)
    assert report.flavor == "jsonschema"
    by = {(f.kind, f.fld): f.severity for f in report.findings}
    assert by[("requirement_changed", "note")] == "breaking"
    assert by[("field_added", "tag")] == "info"   # optional


def test_identical_and_bad_inputs():
    doc = _avro([{"name": "a", "type": "int"}])
    assert diff_topic_schemas(doc, doc).compatible
    with pytest.raises(ValueError, match="not valid JSON"):
        diff_topic_schemas("{", doc)
    with pytest.raises(ValueError, match="neither an Avro"):
        diff_topic_schemas(json.dumps({"x": 1}), doc)
    with pytest.raises(ValueError, match="flavors differ"):
        diff_topic_schemas(doc, json.dumps({"properties": {}}))
    with pytest.raises(ValueError, match="mode"):
        diff_topic_schemas(doc, doc, mode="sideways")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = _demo()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "消息 Schema 对比" in zh and "不兼容" in zh
    assert "Topic Schema Diff" in en and "INCOMPATIBLE" in en
    doc = _avro([{"name": "a", "type": "int"}])
    clean = render_markdown(diff_topic_schemas(doc, doc), lang="en")
    assert "nothing to migrate" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["topicschema", "--old", str(DEMO / "old.json"),
            "--new", str(DEMO / "new.json")]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "消息 Schema 对比" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"compatible": false' in res.output
    res = runner.invoke(cli, args + ["--fail-on-breaking"])
    assert res.exit_code == 1 and "status" in res.output
    res = runner.invoke(cli, ["topicschema", "--old",
                              str(DEMO / "old.json"), "--new",
                              str(DEMO / "old.json"),
                              "--fail-on-breaking"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.topic_schema.tools import (
        topic_schema_diff,
    )

    out = topic_schema_diff(
        (DEMO / "old.json").read_text(encoding="utf-8"),
        (DEMO / "new.json").read_text(encoding="utf-8"), lang="en")
    assert "INCOMPATIBLE" in out and "status" in out
    assert "required" in topic_schema_diff("", "{}")
    assert "bad input" in topic_schema_diff("{", "{}")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.topic_schema.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_diff_and_health():
    client = _client()
    assert client.get("/api/topicschema/health").status_code == 200
    resp = client.post("/api/topicschema/diff", json={
        "old_text": (DEMO / "old.json").read_text(encoding="utf-8"),
        "new_text": (DEMO / "new.json").read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["compatible"] is False
    assert "Topic Schema Diff" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/topicschema/diff",
                       json={"old_text": "{", "new_text": "{}"})
    assert resp.status_code == 400
