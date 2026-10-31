"""Tests for the dq_rulegen agent (generator / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.dq_rulegen import (
    generate_rules,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "dqrulegen_demo" / "orders.csv"


def _demo_draft(**kw):
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return generate_rules(headers, rows, "dwd.orders", **kw)


def _by_type(draft):
    out: dict[str, list] = {}
    for c in draft.checks:
        out.setdefault(c.type, []).append(c)
    return out


# --------------------------------------------------------------- generator

def test_demo_draft_shape():
    draft = _demo_draft()
    by = _by_type(draft)
    assert len(by["row_count"]) == 1
    assert by["unique"][0].columns == ["order_id"]
    enums = {c.column: c.params["allowed"] for c in by["enum_domain"]}
    assert enums["status"] == ["paid", "refund"]
    assert enums["city"] == ["bj", "gz", "sh"]


def test_hollow_column_skipped_entirely():
    draft = _demo_draft()
    assert any("note" in s and "hollow" in s for s in draft.skipped)
    assert all(c.column != "note" and "note" not in c.columns
               for c in draft.checks)


def test_null_headroom_added():
    csv = "k,v\n" + "\n".join(f"{i},{'' if i % 5 == 0 else 'x'}"
                              for i in range(1, 11))
    headers, rows = parse_rows(csv)
    draft = generate_rules(headers, rows, "t")
    (nr,) = [c for c in draft.checks
             if c.type == "null_rate" and c.column == "v"]
    assert nr.params["max_pct"] == 25.0        # 20% observed + 5pp


def test_yaml_roundtrips_through_dqc_parser():
    from seatunnel_agent.agents.data.data_quality.rules import (
        parse_rules_text,
    )

    draft = _demo_draft(where="dt = '${yesterday_pt}'")
    rules, errors = parse_rules_text(draft.yaml_text)
    assert errors == []
    (rule,) = rules
    assert rule.table == "dwd.orders"
    assert rule.where == "dt = '${yesterday_pt}'"
    assert len(rule.checks) == len(draft.checks)


def test_non_identifier_column_skipped():
    headers, rows = parse_rows("订单号,v\n1,a\n2,b\n")
    draft = generate_rules(headers, rows, "t")
    assert any("identifier" in s for s in draft.skipped)
    assert all(c.column != "订单号" for c in draft.checks)


def test_bad_inputs():
    headers, rows = parse_rows("k\n1\n")
    with pytest.raises(ValueError, match="table name"):
        generate_rules(headers, rows, "  ")
    with pytest.raises(ValueError, match="at least one row"):
        generate_rules(headers, [], "t")
    with pytest.raises(ValueError, match="max_change_pct"):
        generate_rules(headers, rows, "t", max_change_pct=0)


# ------------------------------------------------------------------ report

def test_report_both_langs():
    draft = _demo_draft()
    zh = render_markdown(draft, lang="zh")
    en = render_markdown(draft, lang="en")
    assert "质量规则草稿" in zh and "```yaml" in zh
    assert "DQC Rule Draft" in en and "enum_domain" in en
    assert "paid, refund" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_yaml_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["dqrulegen", "-f", str(DEMO),
                              "-t", "dwd.orders"])
    assert res.exit_code == 0, res.output
    assert "质量规则草稿" in res.output
    out = tmp_path / "rules.yaml"
    res = runner.invoke(cli, ["dqrulegen", "-f", str(DEMO),
                              "-t", "dwd.orders", "--yaml-out", str(out),
                              "--format", "json"])
    assert res.exit_code == 0 and '"checks_total": 8' in res.output
    assert out.read_text(encoding="utf-8").startswith("version: 1")


def test_cli_bad_input():
    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["dqrulegen", "--text", "  ",
                                   "-t", "t"])
    assert res.exit_code != 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.dq_rulegen.tools import dq_rulegen

    out = dq_rulegen(DEMO.read_text(encoding="utf-8"), "dwd.orders",
                     lang="en")
    assert "DQC Rule Draft" in out and "enum_domain" in out
    assert "must not be empty" in dq_rulegen("  ", "t")
    assert "must not be empty" in dq_rulegen("k\n1\n", " ")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.dq_rulegen.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_and_health():
    client = _client()
    assert client.get("/api/dqrulegen/health").status_code == 200
    resp = client.post("/api/dqrulegen/generate", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "table": "dwd.orders", "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["checks_total"] == 8
    assert "DQC Rule Draft" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/dqrulegen/generate",
                       json={"data_text": "  ", "table": "t"})
    assert resp.status_code == 400
