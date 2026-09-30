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


# ── round 2: skew_verify / consistency / checksum / limit wrap / audit ─────


def test_run_query_engine_side_limit_wrap(tools, tmp_path):
    _make_db(tmp_path / "a.db",
             "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES "
             + ",".join(f"({i})" for i in range(10)) + ";")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["run_query"]("dev-a", "SELECT id FROM t ORDER BY id", max_rows=3)
    assert "3 rows" in out
    # a query carrying its own LIMIT still works when wrapped
    out2 = tools["run_query"]("dev-a", "SELECT id FROM t LIMIT 5", max_rows=100)
    assert "5 rows" in out2


def test_skew_verify_confirms_hot_key(tools, tmp_path):
    rows = ",".join("('north')" for _ in range(16)) + ",('south'),('east'),('west'),('south')"
    _make_db(tmp_path / "a.db",
             f"CREATE TABLE m (region TEXT); INSERT INTO m VALUES {rows};")
    _save_conn("dev-a", tmp_path / "a.db")
    out = tools["skew_verify"](
        "dev-a", "SELECT region, count(*) FROM m GROUP BY region")
    assert "确认倾斜" in out and "north" in out
    assert "改写模板" in out          # measured rewrite templates included
    assert "SQL 不能为空" in tools["skew_verify"]("dev-a", "  ")


def test_compare_query_results(tools, tmp_path):
    _make_db(tmp_path / "a.db",
             "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1),(2),(3);")
    _save_conn("dev-a", tmp_path / "a.db")
    same = tools["compare_query_results"](
        "dev-a", "SELECT id FROM t", "SELECT id FROM t ORDER BY id DESC")
    assert "✅" in same
    diff = tools["compare_query_results"](
        "dev-a", "SELECT id FROM t", "SELECT id FROM t WHERE id > 1")
    assert "⛔" in diff
    guarded = tools["compare_query_results"](
        "dev-a", "SELECT id FROM t", "DELETE FROM t")
    assert "仅支持单条" in guarded or "single" in guarded.lower()


def test_compare_checksum(tools, tmp_path):
    script = ("CREATE TABLE t (id INTEGER, v TEXT); "
              "INSERT INTO t VALUES (1,'a'),(2,'b'),(3,'c');")
    _make_db(tmp_path / "a.db", script)
    _make_db(tmp_path / "b.db", script)
    # sqlite's fingerprint is length-based (no hash function), so the
    # difference must change a value's LENGTH to be visible there
    _make_db(tmp_path / "c.db",
             "CREATE TABLE t (id INTEGER, v TEXT); "
             "INSERT INTO t VALUES (1,'a'),(2,'bbbb'),(3,'c');")
    _save_conn("dev-a", tmp_path / "a.db")
    _save_conn("dev-b", tmp_path / "b.db")
    _save_conn("dev-c", tmp_path / "c.db")
    assert "✅" in tools["compare_checksum"]("dev-a", "dev-b", "t")
    assert "⛔" in tools["compare_checksum"]("dev-a", "dev-c", "t")
    assert "分号" in tools["compare_checksum"]("dev-a", "dev-b", "t",
                                               where="1=1; --")


def test_audit_log_written(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH", str(audit))
    fns = build_tool_functions()
    fns["sql_transpile"]("SELECT 1", to_dialect="doris")
    fns["list_tables"]("nope")   # error path is audited too
    lines = [json.loads(x) for x in
             audit.read_text(encoding="utf-8").splitlines()]
    assert [r["tool"] for r in lines] == ["sql_transpile", "list_tables"]
    assert lines[0]["ok"] is True
    assert "doris" in lines[0]["args"]
    assert lines[1]["elapsed_ms"] >= 0


def test_data_dictionary_with_sql_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH",
                       str(tmp_path / "audit.jsonl"))
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "a.sql").write_text(
        "INSERT OVERWRITE TABLE dw.ads SELECT id FROM dw.orders;",
        encoding="utf-8")
    fns = build_tool_functions(sql_dir=str(sql_dir))
    out = fns["data_dictionary"]()
    assert "数据字典" in out and "dw.ads" in out


def test_audited_wrapper_converts_exceptions(tmp_path, monkeypatch):
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH",
                       str(tmp_path / "audit.jsonl"))
    from seatunnel_agent.mcp_toolbox import _audited

    def boom(x: int) -> str:
        raise ValueError("nope")

    wrapped = _audited("boom", boom)
    out = wrapped(1)
    assert "内部错误" in out and "ValueError" in out


def test_mcp_server_boot_with_annotations():
    pytest.importorskip("mcp")
    import anyio

    from seatunnel_agent.mcp_toolbox import create_mcp_server

    s = create_mcp_server()
    tool_list = anyio.run(s.list_tools)
    names = {t.name for t in tool_list}
    assert {"sql_review", "run_query", "skew_verify",
            "compare_checksum"} <= names
    rq = next(t for t in tool_list if t.name == "run_query")
    if rq.annotations is not None:          # SDKs with annotation support
        ro = getattr(rq.annotations, "read_only_hint",
                     getattr(rq.annotations, "readOnlyHint", None))
        assert ro is True


# ── round 3: allowlist / no-db / cache self-heal / verify history / stats ──


def test_connections_allowlist(tools, tmp_path, monkeypatch):
    _make_db(tmp_path / "a.db", "CREATE TABLE t (id INTEGER);")
    _make_db(tmp_path / "b.db", "CREATE TABLE t (id INTEGER);")
    _save_conn("dev-a", tmp_path / "a.db")
    _save_conn("prod-x", tmp_path / "b.db")
    fns = build_tool_functions(connections=["dev-a"])
    assert "- t" in fns["list_tables"]("dev-a")
    out = fns["list_tables"]("prod-x")
    assert "白名单" in out
    listing = fns["list_saved_connections"]()
    assert "dev-a" in listing and "prod-x" not in listing


def test_skew_split_key_conn(tools, tmp_path):
    """Split-key check over a NAMED saved connection (issue #21 D): the
    password stays in the preset store, and the sink-side key sub-section
    rides along."""
    db = tmp_path / "spk.db"
    rows = ",".join(
        f"({i}, '{'CN' if i <= 80 else 'US'}', {i * 10})" for i in range(1, 101))
    _make_db(db, "CREATE TABLE orders (id INTEGER, region TEXT, amount INTEGER);"
                 f"INSERT INTO orders VALUES {rows};")
    _save_conn("dev-a", db)
    conf = """
    env { parallelism = 2 }
    source { Jdbc { table_name = "orders", partition_column = "region" } }
    sink { Clickhouse { table = "dw.orders", sharding_key = "region" } }
    """
    out = tools["skew_split_key_conn"]("dev-a", conf)
    assert "SeaTunnel 分片键体检" in out
    assert 'partition_column = "id"' in out       # skewed region → id promoted
    assert "Sink 端键体检" in out and "热点键" in out

    # history carries the measured metrics, source=mcp
    from seatunnel_agent.data_skew.history import default_history
    rec = [r for r in default_history().recent(5) if r.get("mode") == "splitkey"][0]
    assert rec["source"] == "mcp" and rec["splitkey"]["top1_pct"] == 80.0

    # validation: unknown connection / empty config are readable errors
    assert "未找到连接" in tools["skew_split_key_conn"]("nope", conf)
    assert "不能为空" in tools["skew_split_key_conn"]("dev-a", "")


def test_no_db_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH",
                       str(tmp_path / "audit.jsonl"))
    fns = build_tool_functions(include_db=False)
    assert set(fns) == {"sql_review", "sql_transpile", "skew_check",
                        "skew_check_file", "skew_runtime_eventlog",
                        "skew_runtime_history", "impact_diff",
                        "migrate_to_seatunnel"}


def test_dead_connection_cache_self_heals(tools, tmp_path):
    db = tmp_path / "a.db"
    _make_db(db, "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (1);")
    _save_conn("dev-a", db)
    assert "1 rows" in tools["run_query"]("dev-a", "SELECT id FROM t")
    # simulate a schema change the cached handle would miss on some
    # engines: drop the table, query fails, cache is invalidated -> the
    # NEXT call reconnects and sees the recreated table
    import sqlite3
    conn = sqlite3.connect(db)
    conn.executescript("DROP TABLE t;")
    conn.commit(); conn.close()
    out = tools["run_query"]("dev-a", "SELECT id FROM t")
    assert "查询失败" in out
    _make_db(db, "CREATE TABLE t (id INTEGER); INSERT INTO t VALUES (7);")
    ok = tools["run_query"]("dev-a", "SELECT id FROM t")
    assert "1 rows" in ok and "| 7 |" in ok


def test_query_timeout(tools, tmp_path, monkeypatch):
    _make_db(tmp_path / "a.db", "CREATE TABLE t (id INTEGER);")
    _save_conn("dev-a", tmp_path / "a.db")
    monkeypatch.setenv("SEATUNNEL_MCP_QUERY_TIMEOUT", "0.05")
    slow = ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c "
            "WHERE x < 5000000) SELECT COUNT(*) FROM c")
    out = tools["run_query"]("dev-a", slow)
    assert "超时" in out or "timed out" in out


def test_skew_verify_writes_history(tools, tmp_path):
    rows = ",".join("('north')" for _ in range(16)) + ",('south')"
    _make_db(tmp_path / "a.db",
             f"CREATE TABLE m (region TEXT); INSERT INTO m VALUES {rows};")
    _save_conn("dev-a", tmp_path / "a.db")
    tools["skew_verify"]("dev-a", "SELECT region, count(*) FROM m GROUP BY region")
    from seatunnel_agent.data_skew.history import default_history
    recs = default_history().recent()
    assert recs and recs[0]["mode"] == "verify"
    assert recs[0]["source"] == "mcp"
    assert recs[0]["probes"]["confirmed"] >= 1


def test_cli_mcp_stats(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH", str(audit))
    monkeypatch.setenv("SEATUNNEL_DC_PRESETS_PATH",
                       str(tmp_path / "presets.json"))
    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "hist.jsonl"))
    runner = CliRunner()
    empty = runner.invoke(cli, ["mcp-stats"])
    assert empty.exit_code == 0 and "还没有" in empty.output
    fns = build_tool_functions()
    fns["sql_transpile"]("SELECT 1", to_dialect="doris")
    fns["sql_transpile"]("SELECT 1", to_dialect="oracle9000")  # a failure
    res = runner.invoke(cli, ["mcp-stats"])
    assert res.exit_code == 0, res.output
    assert "共 2 次调用" in res.output and "sql_transpile" in res.output


def test_mcp_server_resources():
    pytest.importorskip("mcp")
    import anyio

    from seatunnel_agent.mcp_toolbox import create_mcp_server

    s = create_mcp_server()
    uris = {str(r.uri) for r in anyio.run(s.list_resources)}
    assert "seatunnel://rules/data-skew" in uris
    assert "seatunnel://connections" in uris
    s2 = create_mcp_server(include_db=False)
    uris2 = {str(r.uri) for r in anyio.run(s2.list_resources)}
    assert "seatunnel://connections" not in uris2
    assert len(anyio.run(s2.list_tools)) == 8


def test_server_json_manifest_valid():
    import json

    from seatunnel_agent import __version__

    doc = json.loads(open("server.json", encoding="utf-8").read())
    assert doc["version"] == __version__
    pkg = doc["packages"][0]
    assert pkg["registryType"] == "pypi"
    assert pkg["identifier"] == "seatunnel-agent"
    assert pkg["version"] == __version__
    assert pkg["transport"]["type"] == "stdio"
    # PyPI ownership validation needs the mcp-name marker in the README
    readme = open("README.md", encoding="utf-8").read()
    assert f"mcp-name: {doc['name']}" in readme
