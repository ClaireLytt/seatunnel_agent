# -*- coding: utf-8 -*-
"""Tests for the whole-database sync generator.

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.sync_gen import (SyncPlan, generate_sync,
                                      render_markdown, report_to_dict,
                                      write_outputs)
from seatunnel_agent.sync_gen.model import load_from_ddl
from seatunnel_agent.sync_gen.typemap import UNMAPPED_PREFIX, map_type

DEMO_DDL = Path(__file__).resolve().parents[1] / "examples" / \
    "sync_gen_demo" / "mysql_schema.sql"


def _plan(**kw) -> SyncPlan:
    base = dict(source_mode="ddl", ddl_path=str(DEMO_DDL),
                sink_type="starrocks")
    base.update(kw)
    return SyncPlan(**base)


# ---------------------------------------------------------------------------
# typemap
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mysql,target,expected", [
    ("tinyint(1)", "doris", "BOOLEAN"),
    ("bit(1)", "starrocks", "BOOLEAN"),
    ("tinyint", "doris", "TINYINT"),
    ("int", "hive", "INT"),
    ("int unsigned", "doris", "BIGINT"),
    ("bigint unsigned", "doris", "LARGEINT"),
    ("bigint unsigned", "hive", "DECIMAL(20,0)"),
    ("mediumint", "starrocks", "INT"),
    ("decimal(12, 2)", "doris", "DECIMAL(12,2)"),
    ("decimal(40,2)", "doris", "DECIMAL(38,2)"),
    ("varchar(100)", "starrocks", "VARCHAR(400)"),
    ("varchar(20000)", "doris", "STRING"),
    ("varchar(100)", "hive", "STRING"),
    ("text", "doris", "STRING"),
    ("datetime(3)", "doris", "DATETIME(3)"),
    ("datetime", "hive", "TIMESTAMP"),
    ("timestamp", "starrocks", "DATETIME"),
    ("time", "doris", "STRING"),
    ("year", "doris", "SMALLINT"),
    ("enum('a','b')", "hive", "STRING"),
    ("json", "doris", "JSON"),
    ("json", "hive", "STRING"),
    ("blob", "hive", "BINARY"),
    ("geometry", "doris", "STRING"),
])
def test_map_type(mysql, target, expected):
    mapped, _ = map_type(mysql, target)
    assert mapped == expected


def test_map_type_warnings():
    _, warn = map_type("decimal(40,2)", "doris")
    assert warn and "38" in warn
    _, warn = map_type("geometry", "doris")
    assert warn and warn.startswith(UNMAPPED_PREFIX)
    _, warn = map_type("int", "doris")
    assert warn is None


def test_enum_varchar_sized_by_longest_value():
    mapped, _ = map_type("enum('pending','paid','cancelled')", "starrocks")
    assert mapped == "VARCHAR(36)"  # 'cancelled' = 9 chars × 4


# ---------------------------------------------------------------------------
# model: DDL → TableSpec
# ---------------------------------------------------------------------------

def test_load_from_ddl():
    specs, warnings = load_from_ddl(DEMO_DDL)
    assert not warnings
    by_name = {s.full_name: s for s in specs}
    assert "shop.users" in by_name
    users = by_name["shop.users"]
    assert users.primary_keys == ["id"]
    assert users.comment == "用户表"
    col_names = [c.name for c in users.columns]
    assert col_names[0] == "id"
    assert "phone" in col_names
    phone = next(c for c in users.columns if c.name == "phone")
    assert phone.comment == "手机号"
    # NOT NULL extraction
    created = next(c for c in users.columns if c.name == "created_at")
    assert created.nullable is False
    # 无主键表
    assert by_name["shop.user_address"].primary_keys == []


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------

def test_include_exclude_filters():
    r = generate_sync(_plan(include="users", exclude=r".*_bak$"))
    names = [t.spec.name for t in r.tables]
    assert names == ["users"]
    skipped = dict(r.skipped)
    assert "shop.users_bak" in skipped
    assert "不匹配" in skipped["shop.orders"]


def test_bad_regex_rejected():
    with pytest.raises(ValueError, match="include"):
        generate_sync(_plan(include="("))


# ---------------------------------------------------------------------------
# confgen
# ---------------------------------------------------------------------------

def test_configs_parse_with_pyhocon():
    from pyhocon import ConfigFactory
    r = generate_sync(_plan(pii=True))
    assert r.tables
    for t in r.tables:
        conf = ConfigFactory.parse_string(t.config_text)
        assert conf.get("env")["job.mode"] == "BATCH"


def test_no_pii_no_transform_content():
    r = generate_sync(_plan(pii=False))
    users = next(t for t in r.tables if t.spec.name == "users")
    assert "transform {}" in users.config_text
    assert "md5(" not in users.config_text
    # sink 直接读 src
    assert 'source_table_name = "src"' in users.config_text.split("sink")[1]


def test_pii_transform_injected():
    r = generate_sync(_plan(pii=True))
    users = next(t for t in r.tables if t.spec.name == "users")
    assert "md5(phone) AS phone" in users.config_text
    sink_part = users.config_text.split("sink")[1]
    assert 'source_table_name = "masked"' in sink_part


def test_mask_strategy():
    r = generate_sync(_plan(pii=True, pii_strategy="mask"))
    users = next(t for t in r.tables if t.spec.name == "users")
    assert "concat(substring(phone, 1, 3), '****') AS phone" \
        in users.config_text


def test_no_secrets_only_placeholders():
    r = generate_sync(_plan(pii=True))
    for t in r.tables:
        assert "${mysql_password}" in t.config_text
        assert "${mysql_user}" in t.config_text


# ---------------------------------------------------------------------------
# ddlgen
# ---------------------------------------------------------------------------

def test_starrocks_primary_key_ddl():
    r = generate_sync(_plan())
    users = next(t for t in r.tables if t.spec.name == "users")
    assert "PRIMARY KEY(`id`)" in users.ddl_text
    assert "`id` LARGEINT NOT NULL" in users.ddl_text
    assert 'COMMENT "用户表"' in users.ddl_text


def test_doris_unique_key_and_reorder():
    r = generate_sync(_plan(sink_type="doris"))
    orders = next(t for t in r.tables if t.spec.name == "orders")
    assert "UNIQUE KEY(`order_id`)" in orders.ddl_text
    # key 列排在第一位
    first_col_line = orders.ddl_text.splitlines()[1]
    assert "`order_id`" in first_col_line


def test_no_pk_falls_back_to_duplicate_key():
    r = generate_sync(_plan(sink_type="doris"))
    addr = next(t for t in r.tables if t.spec.name == "user_address")
    assert "DUPLICATE KEY(`user_id`)" in addr.ddl_text
    assert any("无主键" in w for w in addr.warnings)


def test_hive_ddl_has_no_key_clause():
    r = generate_sync(_plan(sink_type="hive"))
    users = next(t for t in r.tables if t.spec.name == "users")
    assert "STORED AS ORC" in users.ddl_text
    assert "KEY" not in users.ddl_text
    assert "COMMENT '手机号'" in users.ddl_text


def test_console_sink_no_ddl():
    r = generate_sync(_plan(sink_type="console"))
    assert all(t.ddl_text is None for t in r.tables)


def test_enum_values_appended_to_comment():
    r = generate_sync(_plan(sink_type="doris"))
    orders = next(t for t in r.tables if t.spec.name == "orders")
    assert "取值: pending/paid/shipped/done/cancelled" in orders.ddl_text


# ---------------------------------------------------------------------------
# pii
# ---------------------------------------------------------------------------

def test_weak_hit_reported_not_masked():
    r = generate_sync(_plan(pii=True))
    addr = next(t for t in r.tables if t.spec.name == "user_address")
    hits = {h.column: h for h in addr.pii_hits}
    assert hits["name"].masked is False          # weak pattern → 只报告
    assert hits["address"].masked is True        # 注释关键词 → 脱敏
    assert "md5(name)" not in addr.config_text
    assert "md5(address) AS address" in addr.config_text


def test_extra_yaml_rules(tmp_path):
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        "rules:\n"
        "  - category: wechat\n"
        "    severity: medium\n"
        "    name_patterns: ['(^|_)wechat(_|$)']\n", encoding="utf-8")
    ddl = tmp_path / "t.sql"
    ddl.write_text(
        "CREATE TABLE db.t (id BIGINT NOT NULL, wechat VARCHAR(64), "
        "PRIMARY KEY (id));", encoding="utf-8")
    r = generate_sync(SyncPlan(source_mode="ddl", ddl_path=str(ddl),
                               pii=True, pii_rules_path=str(rules)))
    hits = r.tables[0].pii_hits
    assert [h.category for h in hits] == ["wechat"]
    assert hits[0].masked


def test_match_column_helper():
    from seatunnel_agent.pii_scan.rules import DEFAULT_RULES, match_column
    hit = match_column("phone", "", DEFAULT_RULES)
    assert hit is not None
    rule, conf, matched_by, _ = hit
    assert rule.category == "phone" and conf == "high" and matched_by == "name"
    assert match_column("order_id", "订单号", DEFAULT_RULES) is None


# ---------------------------------------------------------------------------
# end-to-end: write_outputs + manifest
# ---------------------------------------------------------------------------

def test_write_outputs_layout(tmp_path):
    r = generate_sync(_plan(pii=True, exclude=r".*_(tmp|bak)$"))
    written = write_outputs(r, tmp_path)
    assert (tmp_path / "configs" / "shop__users.conf").is_file()
    assert (tmp_path / "ddl" / "shop__users.sql").is_file()
    manifest = json.loads(
        (tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["tables"] == 4
    assert manifest["pii"]["enabled"] is True
    assert manifest["pii"]["total_masked"] > 0
    assert len(manifest["skipped"]) == 2
    users = next(t for t in manifest["tables"]
                 if t["table"] == "shop.users")
    assert users["primary_keys"] == ["id"]
    assert users["config_file"] == "configs/shop__users.conf"
    assert (tmp_path / "manifest.md").read_text(encoding="utf-8")
    assert all(p.exists() for p in written)


def test_markdown_both_langs():
    r = generate_sync(_plan(pii=True))
    zh = render_markdown(r, "zh")
    en = render_markdown(r, "en")
    assert "全库同步生成器" in zh
    assert "Whole-Database Sync Generator" in en
    assert "shop.users" in zh and "shop.users" in en


def test_pii_off_hint_in_report():
    r = generate_sync(_plan(pii=False))
    assert "--pii" in render_markdown(r, "zh")
    d = report_to_dict(r)
    assert d["pii"]["enabled"] is False
    assert d["pii"]["total_found"] > 0
    assert d["pii"]["total_masked"] == 0


def test_ddl_text_inline():
    ddl = DEMO_DDL.read_text(encoding="utf-8")
    r = generate_sync(SyncPlan(source_mode="ddl", ddl_text=ddl,
                               sink_type="doris"))
    assert len(r.tables) == 6


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_dry_run_ok():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli
    res = CliRunner().invoke(cli, [
        "syncgen", "--ddl", str(DEMO_DDL), "--sink-type", "starrocks",
        "--dry-run", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "全库同步生成器" in res.output


def test_cli_fail_on_unmapped():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli
    res = CliRunner().invoke(cli, [
        "syncgen", "--ddl", str(DEMO_DDL), "--dry-run",
        "--fail-on", "unmapped"])
    assert res.exit_code == 1  # demo 里的 GEOMETRY 列

    res = CliRunner().invoke(cli, [
        "syncgen", "--ddl", str(DEMO_DDL), "--dry-run",
        "--exclude", "user_address", "--fail-on", "unmapped"])
    assert res.exit_code == 0, res.output


def test_cli_fail_on_pii():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli
    res = CliRunner().invoke(cli, [
        "syncgen", "--ddl", str(DEMO_DDL), "--dry-run", "--fail-on", "pii"])
    assert res.exit_code == 1
    res = CliRunner().invoke(cli, [
        "syncgen", "--ddl", str(DEMO_DDL), "--dry-run", "--pii",
        "--fail-on", "pii"])
    assert res.exit_code == 0, res.output


def test_cli_usage_errors():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli
    # --ddl 与 --db 二选一
    res = CliRunner().invoke(cli, ["syncgen", "--dry-run"])
    assert res.exit_code == 2
    # 非 dry-run 必须给 --out
    res = CliRunner().invoke(cli, ["syncgen", "--ddl", str(DEMO_DDL)])
    assert res.exit_code == 2


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.sync_gen.api import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_generate_from_ddl_text(api_client):
    ddl = DEMO_DDL.read_text(encoding="utf-8")
    resp = api_client.post("/api/syncgen/generate", json={
        "ddl_text": ddl, "sink_type": "starrocks", "pii": True,
        "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["manifest"]["summary"]["tables"] == 6
    assert "configs/shop__users.conf" in body["files"]
    assert "ddl/shop__users.sql" in body["files"]
    assert "md5(phone)" in body["files"]["configs/shop__users.conf"]
    assert body["report"]


def test_api_requires_input(api_client):
    resp = api_client.post("/api/syncgen/generate", json={})
    assert resp.status_code == 400


def test_api_path_guard(api_client, monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("SYNCGEN_API_ALLOWED_DIRS", str(allowed))
    resp = api_client.post("/api/syncgen/generate",
                           json={"ddl_path": str(DEMO_DDL)})
    assert resp.status_code in (400, 403)

    ok_ddl = allowed / "t.sql"
    ok_ddl.write_text("CREATE TABLE db.t (id BIGINT, PRIMARY KEY (id));",
                      encoding="utf-8")
    resp = api_client.post("/api/syncgen/generate",
                           json={"ddl_path": str(ok_ddl)})
    assert resp.status_code == 200
    assert resp.json()["manifest"]["summary"]["tables"] == 1


def test_api_health(api_client):
    resp = api_client.get("/api/syncgen/health")
    assert resp.status_code == 200
    assert resp.json()["agent"] == "sync_gen"
