# -*- coding: utf-8 -*-
"""Tests for the PII / sensitive-column scan agent (pii_scan).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.pii_scan import (
    DEFAULT_RULES,
    collect_columns_from_ddl,
    load_extra_rules,
    render_markdown,
    report_to_dict,
    scan_dir,
    scan_sql_text,
)
from seatunnel_agent.pii_scan.rules import expression_is_masked

runner = CliRunner()

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "pii_demo"

DDL = """
CREATE TABLE ods.user_info (
  user_id BIGINT COMMENT '用户ID',
  phone STRING COMMENT '手机号',
  id_card_no STRING COMMENT '身份证号',
  note STRING COMMENT '备注'
) PARTITIONED BY (dt STRING COMMENT '分区日期') STORED AS ORC;
"""


# ─────────────────────────── rules ───────────────────────────

def test_default_rule_catalog_categories():
    cats = {r.category for r in DEFAULT_RULES}
    assert {"phone", "id_card", "bank_card", "email",
            "person_name", "address"} <= cats


@pytest.mark.parametrize("expr,masked", [
    ("MD5(u.phone)", True),
    ("sha2(d.id_card_no, 256) AS h", True),
    ("SUBSTRING(d.email, 1, 3)", True),
    ("regexp_replace(p.phone, '.', '*')", True),
    ("u.phone", False),
    ("", False),
    ("CONCAT(a, b)", False),
    ("md5sum", False),  # not a call of a masking function
])
def test_expression_is_masked(expr, masked):
    assert expression_is_masked(expr) is masked


def test_load_extra_rules(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(
        "rules:\n"
        "  - category: device_token\n"
        "    severity: high\n"
        "    name_patterns: ['(^|_)token($|_)']\n"
        "    comment_keywords: ['令牌']\n",
        encoding="utf-8")
    rules = load_extra_rules(p)
    assert len(rules) == 1
    assert rules[0].category == "device_token"
    assert not rules[0].builtin


@pytest.mark.parametrize("body,err", [
    ("rules:\n  - severity: high\n", "category"),
    ("rules:\n  - category: x\n    severity: nope\n", "severity"),
    ("rules:\n  - category: x\n", "至少需要一个"),
    ("rules:\n  - category: x\n    name_patterns: ['(']\n", "正则无效"),
    ("not a list", "rules"),
])
def test_load_extra_rules_rejects_bad_files(tmp_path, body, err):
    p = tmp_path / "rules.yaml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=err):
        load_extra_rules(p)


# ─────────────────────────── DDL column inventory ───────────────────────────

def test_collect_columns_from_ddl():
    cols, warns = collect_columns_from_ddl(DDL, "hive")
    assert not warns
    by_name = {c.column: c for c in cols}
    assert by_name["phone"].comment == "手机号"
    assert by_name["phone"].table == "ods.user_info"
    assert by_name["dt"].is_partition
    assert not by_name["phone"].is_partition


def test_collect_columns_ddl_parse_error_is_warning():
    cols, warns = collect_columns_from_ddl("CREATE TABLE (((", "hive")
    assert cols == []
    assert warns and "解析失败" in warns[0]


# ─────────────────────────── scanning ───────────────────────────

def test_scan_sql_text_matches_name_and_comment():
    report = scan_sql_text(DDL)
    hits = {(f.table, f.column): f for f in report.findings}
    phone = hits[("ods.user_info", "phone")]
    assert phone.category == "phone"
    assert phone.matched_by == "name+comment"
    assert phone.severity == "high"
    assert ("ods.user_info", "note") not in hits


def test_scan_comment_only_match():
    report = scan_sql_text(
        "CREATE TABLE t (lianxi STRING COMMENT '收件人联系方式');")
    (f,) = report.findings
    assert f.matched_by == "comment"
    assert f.category == "phone"


def test_unmasked_spread_escalates_severity():
    report = scan_sql_text(
        "CREATE TABLE ods.u (email STRING COMMENT '邮箱');\n"
        "INSERT OVERWRITE TABLE dwd.u SELECT email FROM ods.u;")
    f = next(x for x in report.findings
             if (x.table, x.column) == ("ods.u", "email"))
    assert f.base_severity == "medium"
    assert f.severity == "high"          # escalated by unmasked spread
    assert len(f.unmasked_edges) == 1
    assert f.impacted == ["dwd.u.email"]


def test_masked_spread_does_not_escalate():
    report = scan_sql_text(
        "CREATE TABLE ods.u (email STRING COMMENT '邮箱');\n"
        "INSERT OVERWRITE TABLE dwd.u SELECT md5(email) AS email_x FROM ods.u;")
    f = next(x for x in report.findings
             if (x.table, x.column) == ("ods.u", "email"))
    assert f.severity == f.base_severity == "medium"
    assert len(f.masked_edges) == 1 and not f.unmasked_edges


def test_masked_name_demoted_to_low():
    report = scan_sql_text("CREATE TABLE t (phone_md5 STRING);")
    (f,) = report.findings
    assert f.severity == "low" and f.confidence == "low"


def test_weak_name_match_is_low_confidence_and_never_escalates():
    report = scan_sql_text(
        "CREATE TABLE ods.u (name STRING);\n"
        "INSERT OVERWRITE TABLE dwd.u SELECT name FROM ods.u;")
    f = next(x for x in report.findings
             if (x.table, x.column) == ("ods.u", "name"))
    assert f.confidence == "low"
    assert f.severity == f.base_severity  # no escalation on weak matches


def test_scan_demo_dir():
    report = scan_dir(DEMO_DIR)
    c = report.counts()
    assert c["total"] >= 10
    assert c["high"] >= 5
    # the showcase finding: bank card spreads unmasked to the ads layer
    f = next(x for x in report.findings
             if (x.table, x.column) == ("ods.order_pay", "bank_card_no"))
    assert any(e.dst == "ads.pay_report.bank_card_no" and not e.masked
               for e in f.spread_edges)


def test_scan_missing_dir_returns_warning(tmp_path):
    report = scan_dir(tmp_path / "empty")
    assert not report.findings
    assert report.warnings


def test_custom_rule_applies():
    rules = list(DEFAULT_RULES) + load_extra_rules_from_text(
        "rules:\n  - category: device_token\n    severity: high\n"
        "    name_patterns: ['(^|_)token($|_)']\n")
    report = scan_sql_text("CREATE TABLE t (push_token STRING);",
                           rules=rules)
    assert any(f.category == "device_token" for f in report.findings)


def load_extra_rules_from_text(text: str):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "r.yaml"
        p.write_text(text, encoding="utf-8")
        return load_extra_rules(p)


# ─────────────────────────── rendering ───────────────────────────

def test_render_markdown_zh_and_en():
    report = scan_sql_text(DDL)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "敏感数据扫描" in zh and "手机号】" in zh
    assert "PII / Sensitive Column Scan" in en and "Phone number" in en


def test_render_markdown_clean():
    report = scan_sql_text("CREATE TABLE t (order_id BIGINT, amount DOUBLE);")
    assert "未命中" in render_markdown(report, "zh")


def test_report_to_dict_carries_labels():
    report = scan_sql_text(DDL)
    data = report_to_dict(report, "en")
    assert data["counts"]["total"] == len(report.findings)
    assert all("category_label" in f for f in data["findings"])
    json.dumps(data)  # payload must be JSON-serializable


# ─────────────────────────── CLI ───────────────────────────

def test_cli_pii_inline():
    r = runner.invoke(cli, ["pii", "--sql",
                            "CREATE TABLE t (phone STRING COMMENT '手机号');"])
    assert r.exit_code == 0, r.output
    assert "敏感数据扫描" in r.output


def test_cli_pii_requires_a_source():
    r = runner.invoke(cli, ["pii"])
    assert r.exit_code != 0
    assert "--dir" in r.output


def test_cli_pii_json_and_fail_on(tmp_path):
    out = tmp_path / "report.json"
    r = runner.invoke(cli, [
        "pii", "--dir", str(DEMO_DIR), "-F", "json",
        "--fail-on", "high", "-o", str(out)])
    assert r.exit_code == 1          # demo dir carries high findings
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["high"] >= 1


def test_cli_pii_fail_on_passes_when_clean():
    r = runner.invoke(cli, ["pii", "--sql",
                            "CREATE TABLE t (order_id BIGINT);",
                            "--fail-on", "low"])
    assert r.exit_code == 0, r.output


def test_cli_pii_custom_rules(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n  - category: device_token\n    severity: high\n"
        "    name_patterns: ['(^|_)token($|_)']\n", encoding="utf-8")
    r = runner.invoke(cli, ["pii", "--sql",
                            "CREATE TABLE t (push_token STRING);",
                            "--rules", str(rules), "--lang", "en"])
    assert r.exit_code == 0, r.output
    assert "device_token" in r.output


# ─────────────────────────── REST API ───────────────────────────

@pytest.fixture()
def api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.pii_scan.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline(api_client):
    r = api_client.post("/api/pii/scan", json={
        "sql": "CREATE TABLE t (phone STRING COMMENT '手机号');",
        "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["total"] == 1
    assert "Phone number" in data["report"]


def test_api_scan_dir_whitelisted(api_client):
    r = api_client.post("/api/pii/scan", json={"dir": str(DEMO_DIR)})
    # DEMO_DIR sits under the repo cwd → allowed by the default whitelist
    assert r.status_code == 200
    assert r.json()["result"]["counts"]["high"] >= 1


def test_api_scan_dir_outside_whitelist(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("PII_API_ALLOWED_DIRS", str(tmp_path / "only_here"))
    r = api_client.post("/api/pii/scan", json={"dir": str(DEMO_DIR)})
    assert r.status_code == 403


def test_api_scan_requires_input(api_client):
    r = api_client.post("/api/pii/scan", json={})
    assert r.status_code == 400


def test_api_rules_and_health(api_client):
    r = api_client.get("/api/pii/rules")
    assert r.status_code == 200
    assert any(x["category"] == "phone" for x in r.json()["rules"])
    assert api_client.get("/api/pii/health").json()["status"] == "ok"
