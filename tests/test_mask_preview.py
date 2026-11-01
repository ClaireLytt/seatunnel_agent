"""Tests for the mask_preview agent (masker / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.mask_preview import (
    mask_value,
    preview_mask,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "maskpreview_demo" / "users.csv"


def _demo_preview():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return preview_mask(headers, rows)


# ------------------------------------------------------------------ masker

def test_mask_value_families():
    assert mask_value("phone", "13812340001") == "138****0001"
    assert mask_value("id_card",
                      "110101199003071234") == "110101********1234"
    assert mask_value("email", "xiaoming@example.com") == "x***@example.com"
    assert mask_value("bank_card",
                      "6222020200112233445") == "**** **** **** 3445"
    assert mask_value("person_name", "王小明") == "王**"
    assert mask_value("address", "北京市朝阳区幸福路1号") == "北京市朝阳区****"
    assert mask_value("salary", "25000") == "***"
    assert mask_value("ip_address", "10.1.2.3") == "10.1.*.*"
    assert mask_value("passport", "E12345678") == "E*******8"
    assert mask_value("phone", None) is None
    assert mask_value("phone", "") == ""


def test_demo_detects_four_sensitive_columns():
    preview = _demo_preview()
    names = {c.name: c for c in preview.columns}
    assert set(names) == {"mobile", "id_card", "email", "user_name"}
    assert names["mobile"].detected_by == "name+value"
    assert names["user_name"].detected_by == "name"
    assert names["mobile"].severity == "high"
    assert not preview.clean


def test_value_only_detection():
    csv = "contact,note\n13812340001,hello\n15998765432,world\n"
    headers, rows = parse_rows(csv)
    preview = preview_mask(headers, rows)
    (c,) = preview.columns
    assert c.name == "contact" and c.category == "phone"
    assert c.detected_by == "value"
    assert preview.masked_rows[0]["contact"] == "138****0001"
    assert preview.masked_rows[0]["note"] == "hello"


def test_clean_sample_passes_through():
    headers, rows = parse_rows("order_id,amount\n1,2.5\n")
    preview = preview_mask(headers, rows)
    assert preview.clean
    assert preview.masked_rows[0] == {"order_id": "1", "amount": "2.5"}


def test_preview_rows_clip_and_bad_inputs():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    preview = preview_mask(headers, rows, preview_rows=2)
    assert len(preview.masked_rows) == 2
    with pytest.raises(ValueError, match="no columns"):
        preview_mask([], [])
    with pytest.raises(ValueError, match="preview_rows"):
        preview_mask(headers, rows, preview_rows=0)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    preview = _demo_preview()
    zh = render_markdown(preview, lang="zh")
    en = render_markdown(preview, lang="en")
    assert "脱敏预览" in zh and "138****0001" in zh
    assert "Mask Preview" in en and "id_card" in en
    headers, rows = parse_rows("order_id,amount\n1,2.5\n")
    clean = render_markdown(preview_mask(headers, rows), lang="en")
    assert "No sensitive columns" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["maskpreview", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "脱敏预览" in res.output
    res = runner.invoke(cli, ["maskpreview", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"sensitive_columns": 4' in res.output
    res = runner.invoke(cli, ["maskpreview", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["maskpreview", "--text",
                              "order_id,amount\n1,2.5",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.mask_preview.tools import mask_preview

    out = mask_preview(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "138****0001" in out and "id_card" in out
    assert "must not be empty" in mask_preview("  ")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.mask_preview.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_preview_and_health():
    client = _client()
    assert client.get("/api/maskpreview/health").status_code == 200
    resp = client.post("/api/maskpreview/preview",
                       json={"data_text": DEMO.read_text(encoding="utf-8"),
                             "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["sensitive_columns"] == 4
    assert "Mask Preview" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/maskpreview/preview",
                       json={"data_text": "   "})
    assert resp.status_code == 400
