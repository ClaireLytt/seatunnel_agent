# -*- coding: utf-8 -*-
"""Unified MCP toolbox (seatunnel-agent mcp) — the tool callables are plain
functions, so everything here runs without the ``mcp`` package."""

from __future__ import annotations

import sqlite3

import pytest

from seatunnel_agent.mcp_toolbox import build_tool_functions


@pytest.fixture()
def tools(tmp_path, monkeypatch):
    """Toolbox wired to an isolated preset store + skew history."""
    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "skew_hist.jsonl"))
    return build_tool_functions()


def _make_db(path, script):
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.commit()
    conn.close()


def _save_conn(name, db_path):
    import os

    from seatunnel_agent.data_comparison.presets import ConnectionPresetsStore

    store = ConnectionPresetsStore(os.environ["SEATUNNEL_DC_PRESETS_PATH"])
    store.save(name=name, ds_type="sqlite", host="", port=0,
               database=str(db_path))


# ── pure-static tools ──────────────────────────────────────────────────────


def test_sql_review_static(tools):
    out = tools["sql_review"]("SELECT * FROM ods.t WHERE substr(dt,1,7)='2024-06'")
    assert "SELECT *" in out
    assert "不能为空" in tools["sql_review"]("  ")
    assert "unknown dialect" in tools["sql_review"]("SELECT 1", dialect="oracle")


def test_sql_review_with_ddl_schema_check(tools):
    out = tools["sql_review"](
        "SELECT user_id FROM ods.user_log WHERE amount > 10",
        ddl="CREATE TABLE ods.user_log (user_id BIGINT, amount DOUBLE) "
            "PARTITIONED BY (dt STRING);")
    assert "分区" in out


def test_sql_transpile(tools):
    out = tools["sql_transpile"](
        "SELECT get_json_object(payload, '$.a') FROM t", to_dialect="doris")
    assert "doris" in out.lower()
    assert "不能为空" in tools["sql_transpile"]("", to_dialect="doris")
    assert "翻译失败" in tools["sql_transpile"]("SELECT 1", to_dialect="oracle9000")


def test_skew_tools_included(tools):
    out = tools["skew_check"]("SELECT count(distinct uid) FROM t")
    assert "数据倾斜分析报告" in out


def test_impact_diff(tools):
    old = "INSERT OVERWRITE TABLE dw.ads SELECT id, amount FROM dw.orders;"
    new = "INSERT OVERWRITE TABLE dw.ads SELECT id, amount * 2 AS amount FROM dw.orders;"
    out = tools["impact_diff"](old, new)
    assert "dw.ads" in out
    assert "required" in tools["impact_diff"]("", "SELECT 1")


def test_migrate_auto_detects_datax_and_sqoop(tools):
    datax = ('{"job": {"content": [{"reader": {"name": "mysqlreader", '
             '"parameter": {"username": "u", "connection": [{"jdbcUrl": '
             '["jdbc:mysql://h:3306/db"], "table": ["t"]}]}}, "writer": '
             '{"name": "hdfswriter", "parameter": {}}}]}}')
    out = tools["migrate_to_seatunnel"](datax)
    assert "source" in out.lower() or "Jdbc" in out
    out2 = tools["migrate_to_seatunnel"](
        "sqoop import --connect jdbc:mysql://h/db --table t")
    assert "sqoop" in out2.lower() or "Jdbc" in out2
    assert "source_kind" in tools["migrate_to_seatunnel"]("x", source_kind="nope")
    assert "不能为空" in tools["migrate_to_seatunnel"]("   ")


# ── database tools over named connections ──────────────────────────────────


def test_unknown_connection_lists_saved_names(tools, tmp_path):
    _make_db(tmp_path / "a.db", "CREATE TABLE t1 (id INTEGER);")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["list_tables"]("nope")
    assert "未找到连接" in out and "dev-a" in out


def test_list_saved_connections(tools, tmp_path):
    assert "暂无已保存连接" in tools["list_saved_connections"]()
    _make_db(tmp_path / "a.db", "CREATE TABLE t1 (id INTEGER);")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["list_saved_connections"]()
    assert "dev-a" in out and "sqlite" in out


def test_list_tables_and_schema(tools, tmp_path):
    _make_db(tmp_path / "a.db",
             "CREATE TABLE orders (id INTEGER, amount REAL);"
             "CREATE TABLE users (id INTEGER, name TEXT);")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["list_tables"]("dev-a")
    assert "orders" in out and "users" in out
    assert "users" not in tools["list_tables"]("dev-a", keyword="ord")
    schema = tools["table_schema"]("dev-a", "orders")
    assert "amount" in schema
    assert "非法表名" in tools["table_schema"]("dev-a", "x; drop table t")


def test_run_query_read_only_guard(tools, tmp_path):
    _make_db(tmp_path / "a.db",
             "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1),(2);")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["run_query"]("dev-a", "SELECT id FROM t ORDER BY id")
    assert "| id |" in out and "2 rows" in out
    # writes and multi-statement scripts are refused
    assert "只读" in tools["run_query"]("dev-a", "DELETE FROM t")
    assert "只读" in tools["run_query"]("dev-a", "SELECT 1; SELECT 2")
    # row cap
    capped = tools["run_query"]("dev-a", "SELECT id FROM t", max_rows=1)
    assert "1 rows" in capped


def test_compare_row_count(tools, tmp_path):
    _make_db(tmp_path / "a.db",
             "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1),(2),(3);")
    _make_db(tmp_path / "b.db",
             "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1),(2);")
    _save_conn("dev-a", tmp_path / "a.db")
    _save_conn("dev-b", tmp_path / "b.db")
    out = tools["compare_row_count"]("dev-a", "dev-b", "t")
    assert "⛔" in out and "-1" in out
    same = tools["compare_row_count"]("dev-a", "dev-b", "t", where="id <= 2")
    assert "✅" in same
    assert "分号" in tools["compare_row_count"]("dev-a", "dev-b", "t",
                                                where="1=1; drop table t")
    assert "非法表名" in tools["compare_row_count"]("dev-a", "dev-b", "t; --")


def test_compare_schema(tools, tmp_path):
    _make_db(tmp_path / "a.db", "CREATE TABLE t (id INTEGER, name TEXT);")
    _make_db(tmp_path / "b.db",
             "CREATE TABLE t (id INTEGER, name REAL, extra TEXT);")
    _save_conn("dev-a", tmp_path / "a.db")
    _save_conn("dev-b", tmp_path / "b.db")
    out = tools["compare_schema"]("dev-a", "dev-b", "t")
    assert "extra" in out and "类型差异" in out
    _make_db(tmp_path / "c.db", "CREATE TABLE t (id INTEGER, name TEXT);")
    _save_conn("dev-c", tmp_path / "c.db")
    assert "✅" in tools["compare_schema"]("dev-a", "dev-c", "t")


# ── lineage tools are opt-in ───────────────────────────────────────────────


def test_lineage_tools_only_with_source(tmp_path, monkeypatch):
    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    base = build_tool_functions()
    assert not any(n.startswith("lineage_") for n in base)
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dw.ads SELECT id FROM dw.orders;",
        encoding="utf-8")
    with_lin = build_tool_functions(sql_dir=str(sql_dir))
    assert any(n.startswith("lineage_") for n in with_lin)
    out = with_lin["lineage_query"]("dw.ads")
    assert "dw.orders" in out
