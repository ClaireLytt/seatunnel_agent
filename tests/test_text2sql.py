"""Tests for the Text2SQL (Chat BI) package: schema parsing, SQL safety
validation, table/column matching, partition rules, CSV export, and tools."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.text2sql.validator import (
    enforce_limit,
    extract_tables,
    validate_columns,
    validate_sql,
)
from seatunnel_agent.text2sql.matcher import match_tables, match_columns, tokenize
from seatunnel_agent.text2sql.partition import (
    TimeRange,
    build_partition_clause,
    classify_table,
    extract_time_range,
    has_partition_filter,
)
from seatunnel_agent.text2sql.exporter import export_csv
from seatunnel_agent.text2sql.qlog import QueryLogger
from seatunnel_agent.text2sql.tools import (
    Text2SQLRuntime,
    execute_text2sql_tool,
)
from seatunnel_agent.text2sql.executor import DatabaseConfig, QueryResult


_DDL = """
-- comment line
CREATE TABLE zz.dwm_scm_detail_di(
  inbound_id string COMMENT '主键',
  warehouse_name string COMMENT '仓库名称',
  inbound_cnt bigint COMMENT '入库数量',
  inbound_create_time string COMMENT '入库创建时间',
  amount decimal(10,2) COMMENT '金额',
  tags array<string> COMMENT '标签列表'
)
COMMENT '供应链域全流程明细表'
PARTITIONED BY (pt string COMMENT '分区日期yyyyMMdd');

CREATE TABLE zz.dws_scm_attribution_df(
  level1_category_name string COMMENT '商品一级类目',
  scm_inbound_cnt bigint COMMENT '供应链入库量'
)
COMMENT '供应链效率归因表'
PARTITIONED BY (pt string COMMENT '分区');

CREATE TABLE atest.student(
  id int COMMENT '学号',
  name string COMMENT '姓名'
)
COMMENT '学生表';
"""


@pytest.fixture()
def store() -> SchemaStore:
    return SchemaStore(parse_ddl(_DDL))


# ------------------------------------------------------------------
# Schema parsing
# ------------------------------------------------------------------

class TestParseDDL:
    def test_parses_all_tables(self, store):
        assert len(store) == 3
        assert store.get("zz.dwm_scm_detail_di") is not None
        assert store.get("ZZ.DWM_SCM_DETAIL_DI") is not None  # case-insensitive

    def test_table_comment_and_type(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        assert t.comment == "供应链域全流程明细表"
        assert t.table_type == "incremental"
        assert store.get("zz.dws_scm_attribution_df").table_type == "full"
        assert store.get("atest.student").table_type == "other"

    def test_columns_with_complex_types(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        names = {c.name for c in t.columns}
        assert {"inbound_id", "amount", "tags"} <= names
        assert t.find_column("amount").dtype.startswith("decimal")
        assert "array" in t.find_column("tags").dtype

    def test_partition_columns(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        assert t.is_partitioned
        assert t.partition_columns[0].name == "pt"
        assert not store.get("atest.student").is_partitioned

    def test_find_column_by_comment(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        assert t.find_column_by_comment("仓库名称").name == "warehouse_name"


# ------------------------------------------------------------------
# SQL validation (PRD section 9)
# ------------------------------------------------------------------

class TestValidateSQL:
    def test_valid_select(self, store):
        r = validate_sql(
            "SELECT warehouse_name FROM zz.dwm_scm_detail_di WHERE pt='20260312'",
            store,
        )
        assert r.ok
        assert r.tables == ["zz.dwm_scm_detail_di"]

    @pytest.mark.parametrize("sql", [
        "DROP TABLE zz.dwm_scm_detail_di",
        "DELETE FROM zz.dwm_scm_detail_di",
        "UPDATE zz.dwm_scm_detail_di SET a=1",
        "INSERT INTO zz.dwm_scm_detail_di VALUES (1)",
        "TRUNCATE TABLE zz.dwm_scm_detail_di",
        "CREATE TABLE hacked AS SELECT 1",
    ])
    def test_rejects_write_statements(self, sql, store):
        assert not validate_sql(sql, store).ok

    def test_rejects_stacked_queries(self, store):
        r = validate_sql(
            "SELECT 1 FROM atest.student; DROP TABLE atest.student", store
        )
        assert not r.ok

    def test_rejects_non_whitelisted_table(self, store):
        r = validate_sql("SELECT * FROM secret.users", store)
        assert not r.ok
        assert any("whitelist" in e for e in r.errors)

    def test_keyword_inside_string_literal_is_ok(self, store):
        r = validate_sql(
            "SELECT * FROM atest.student WHERE name = 'drop table'", store
        )
        assert r.ok

    def test_cte_names_not_flagged(self, store):
        sql = (
            "WITH s AS (SELECT id FROM atest.student) "
            "SELECT * FROM s JOIN atest.student t ON s.id = t.id"
        )
        r = validate_sql(sql, store)
        assert r.ok, r.errors

    def test_extract_tables_join(self):
        tables = extract_tables(
            "SELECT * FROM atest.student a JOIN atest.student2 b ON a.id=b.id"
        )
        assert tables == ["atest.student", "atest.student2"]


class TestEnforceLimit:
    def test_appends_default_limit(self):
        assert enforce_limit("SELECT 1").endswith("LIMIT 1000")

    def test_keeps_existing_limit(self):
        assert enforce_limit("SELECT 1 LIMIT 10") == "SELECT 1 LIMIT 10"

    def test_caps_excessive_limit(self):
        assert enforce_limit("SELECT 1 LIMIT 999999999").endswith("LIMIT 100000")


# ------------------------------------------------------------------
# Matching (PRD 6.1)
# ------------------------------------------------------------------

class TestMatcher:
    def test_tokenize_mixed(self):
        english, ngrams = tokenize("查询 atest.student 的入库单量")
        assert "atest.student" in english
        assert any("入库" in g for g in ngrams)

    def test_matches_by_chinese_comment(self, store):
        matches = match_tables("查询供应链域全流程明细表中最近30天的入库单量", store)
        assert matches
        assert matches[0].table.full_name == "zz.dwm_scm_detail_di"

    def test_matches_by_english_name(self, store):
        matches = match_tables("select from atest.student", store)
        assert matches[0].table.full_name == "atest.student"

    def test_full_table_match(self, store):
        matches = match_tables("供应链效率归因表中商品一级类目的供应链入库量", store)
        assert matches[0].table.full_name == "zz.dws_scm_attribution_df"

    def test_match_columns_prefers_english_name(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        results = match_columns("warehouse_name 的入库数量", t)
        by_name = [r for r in results if r.matched_by == "name"]
        assert by_name and by_name[0].column.name == "warehouse_name"
        by_comment = [r for r in results if r.matched_by == "comment"]
        assert any(r.column.name == "inbound_cnt" for r in by_comment)


# ------------------------------------------------------------------
# Partition rules (PRD 4 / 6.3)
# ------------------------------------------------------------------

class TestPartition:
    def test_classify(self):
        assert classify_table("a_di") == "incremental"
        assert classify_table("a_hf") == "full"
        assert classify_table("student") == "other"

    def test_extract_recent_days(self):
        tr = extract_time_range("最近30天的入库单量", today=date(2026, 3, 13))
        assert tr.start == date(2026, 2, 11)
        assert tr.end == date(2026, 3, 13)

    def test_extract_exact_date(self):
        tr = extract_time_range("日期为20260312的数据")
        assert tr.start == tr.end == date(2026, 3, 12)

    def test_extract_chinese_date(self):
        tr = extract_time_range("2026年3月12日的数据")
        assert tr.start == date(2026, 3, 12)

    def test_incremental_with_range(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        clause = build_partition_clause(
            t, TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 13))
        )
        assert clause == "pt >= '20260301' AND pt <= '20260313'"

    def test_incremental_without_range_uses_max(self, store):
        t = store.get("zz.dwm_scm_detail_di")
        assert build_partition_clause(t, None, max_partition="20260313") == \
            "pt = '20260313'"

    def test_full_table_prefers_user_date(self, store):
        t = store.get("zz.dws_scm_attribution_df")
        clause = build_partition_clause(
            t, TimeRange(start=date(2026, 3, 12), end=date(2026, 3, 12))
        )
        assert clause == "pt = '20260312'"

    def test_unpartitioned_returns_empty(self, store):
        assert build_partition_clause(store.get("atest.student")) == ""

    def test_has_partition_filter(self):
        assert has_partition_filter("SELECT * FROM t WHERE pt = '20260312'")
        assert not has_partition_filter("SELECT * FROM t WHERE id = 1")


# ------------------------------------------------------------------
# Export & logging
# ------------------------------------------------------------------

class TestExportAndLog:
    def test_export_csv_to_dir(self, tmp_path):
        path = export_csv(
            columns=["仓库", "数量"],
            rows=[("北京仓", 10), ("上海仓", 20)],
            path=str(tmp_path),
            name_hint="入库单量",
        )
        out = Path(path)
        assert out.is_file() and out.suffix == ".csv"
        content = out.read_text(encoding="utf-8-sig")
        assert "仓库" in content and "北京仓" in content

    def test_export_csv_explicit_file(self, tmp_path):
        target = tmp_path / "sub" / "result.csv"
        path = export_csv(["a"], [(1,)], path=str(target))
        assert Path(path).name == "result.csv"

    def test_query_logger_roundtrip(self, tmp_path):
        logger = QueryLogger(log_dir=tmp_path)
        logger.log(
            user_query="查入库量", generated_sql="SELECT 1", status="success",
            matched_tables=["zz.t"], exec_time_ms=42, row_count=3,
        )
        records = logger.recent(5)
        assert len(records) == 1
        rec = records[0]
        assert rec["status"] == "success"
        assert rec["row_count"] == 3
        # file is valid JSON lines
        line = (tmp_path / "text2sql_queries.jsonl").read_text(encoding="utf-8")
        assert json.loads(line.strip())["user_query"] == "查入库量"


# ------------------------------------------------------------------
# Column validation (PRD §13 — prevent hallucinated columns)
# ------------------------------------------------------------------

class TestValidateColumns:
    def test_valid_columns_no_warnings(self, store):
        sql = "SELECT warehouse_name FROM zz.dwm_scm_detail_di WHERE pt = '20260312'"
        warnings = validate_columns(sql, store)
        assert not warnings

    def test_detects_nonexistent_column(self, store):
        sql = "SELECT fake_column FROM zz.dwm_scm_detail_di WHERE pt = '20260312'"
        warnings = validate_columns(sql, store)
        assert any("fake_column" in w for w in warnings)

    def test_partition_column_not_flagged(self, store):
        sql = "SELECT warehouse_name FROM zz.dwm_scm_detail_di WHERE pt = '20260312'"
        warnings = validate_columns(sql, store)
        assert not any("pt" in w for w in warnings)

    def test_validate_sql_populates_column_warnings(self, store):
        sql = "SELECT bogus_col FROM atest.student WHERE id = 1"
        result = validate_sql(sql, store)
        assert result.ok
        assert any("bogus_col" in w for w in result.column_warnings)

    def test_no_warnings_for_empty_query(self, store):
        warnings = validate_columns("SELECT 1", store)
        assert not warnings


# ------------------------------------------------------------------
# Partition filter enforcement (PRD §6.3 / §9)
# ------------------------------------------------------------------

class TestPartitionEnforcement:
    @pytest.fixture()
    def runtime(self, store, tmp_path):
        rt = Text2SQLRuntime(store=store, logger=QueryLogger(log_dir=tmp_path))
        return rt

    def test_rejects_missing_partition_filter(self, runtime):
        result_str = execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT warehouse_name FROM zz.dwm_scm_detail_di"},
            runtime,
        )
        result = json.loads(result_str)
        assert "error" in result
        assert "partition filter" in result["error"].lower()

    def test_accepts_query_with_partition_filter(self, runtime):
        result_str = execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT warehouse_name FROM zz.dwm_scm_detail_di WHERE pt = '20260312'"},
            runtime,
        )
        result = json.loads(result_str)
        # Will fail on execution (no Hive) but should not be rejected for partition
        assert "partition filter" not in result.get("error", "").lower()

    def test_unpartitioned_table_no_enforcement(self, runtime):
        result_str = execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT id FROM atest.student"},
            runtime,
        )
        result = json.loads(result_str)
        assert "partition filter" not in result.get("error", "").lower()


# ------------------------------------------------------------------
# Tool layer (tools.py)
# ------------------------------------------------------------------

class TestTools:
    @pytest.fixture()
    def runtime(self, store, tmp_path):
        return Text2SQLRuntime(store=store, logger=QueryLogger(log_dir=tmp_path))

    def test_match_tables_tool(self, runtime):
        result_str = execute_text2sql_tool(
            "match_tables",
            {"query": "供应链域全流程明细表"},
            runtime,
        )
        data = json.loads(result_str)
        assert data["count"] > 0
        assert data["candidates"][0]["table"] == "zz.dwm_scm_detail_di"

    def test_get_table_schema_tool(self, runtime):
        result_str = execute_text2sql_tool(
            "get_table_schema",
            {"table": "zz.dwm_scm_detail_di"},
            runtime,
        )
        data = json.loads(result_str)
        assert data["table"] == "zz.dwm_scm_detail_di"
        assert data["partitioned"] is True
        assert data["table_type"] == "incremental"
        col_names = {c["name"] for c in data["columns"]}
        assert "warehouse_name" in col_names

    def test_get_table_schema_unknown_table(self, runtime):
        result_str = execute_text2sql_tool(
            "get_table_schema",
            {"table": "unknown.table"},
            runtime,
        )
        data = json.loads(result_str)
        assert "error" in data

    def test_get_max_partition_unpartitioned(self, runtime):
        result_str = execute_text2sql_tool(
            "get_max_partition",
            {"table": "atest.student"},
            runtime,
        )
        data = json.loads(result_str)
        assert "error" in data
        assert "not partitioned" in data["error"]

    def test_export_csv_no_result(self, runtime):
        result_str = execute_text2sql_tool("export_csv", {}, runtime)
        data = json.loads(result_str)
        assert "error" in data

    def test_export_csv_with_result(self, runtime, tmp_path):
        runtime.last_result = QueryResult(
            columns=["name", "age"], rows=[("Alice", 30)],
            elapsed_ms=10, row_count=1,
        )
        result_str = execute_text2sql_tool(
            "export_csv",
            {"path": str(tmp_path)},
            runtime,
        )
        data = json.loads(result_str)
        assert data["success"] is True
        assert Path(data["csv_path"]).is_file()

    def test_unknown_tool(self, runtime):
        result_str = execute_text2sql_tool("nonexistent", {}, runtime)
        data = json.loads(result_str)
        assert "error" in data


# ------------------------------------------------------------------
# Additional edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_cte_with_join(self, store):
        sql = (
            "WITH a AS (SELECT id FROM atest.student) "
            "SELECT a.id, s.name FROM a "
            "JOIN atest.student s ON a.id = s.id"
        )
        r = validate_sql(sql, store)
        assert r.ok, r.errors

    def test_extract_time_range_english(self):
        tr = extract_time_range("data from last 7 days", today=date(2026, 3, 13))
        assert tr.start == date(2026, 3, 6)
        assert tr.end == date(2026, 3, 13)

    def test_extract_time_range_past_days(self):
        tr = extract_time_range("past 14 days metrics", today=date(2026, 3, 13))
        assert tr.start == date(2026, 2, 27)

    def test_extract_time_range_no_match(self):
        tr = extract_time_range("所有学生信息")
        assert tr.is_empty

    def test_extract_time_range_month_day(self):
        tr = extract_time_range("3月12日的数据")
        assert tr.start.month == 3
        assert tr.start.day == 12

    def test_matcher_empty_query(self, store):
        matches = match_tables("", store)
        assert matches == []

    def test_matcher_tie_breaks_by_column_hits(self, store):
        matches = match_tables("入库数量 仓库名称", store)
        if len(matches) > 1:
            top = matches[0]
            assert top.column_hit_count >= matches[1].column_hit_count

    def test_has_partition_filter_between(self):
        assert has_partition_filter(
            "SELECT * FROM t WHERE pt between '20260301' AND '20260313'"
        )

    def test_has_partition_filter_in(self):
        assert has_partition_filter(
            "SELECT * FROM t WHERE pt in ('20260301', '20260302')"
        )

    def test_enforce_limit_preserves_semicolons(self):
        result = enforce_limit("SELECT 1;")
        assert "LIMIT 1000" in result
        assert ";" not in result


# ------------------------------------------------------------------
# Cross-year date extraction
# ------------------------------------------------------------------

class TestCrossYearDate:
    def test_month_day_future_rolls_back(self):
        """'12月31日' queried on Jan 5 should give last year's Dec 31."""
        tr = extract_time_range("12月31日的数据", today=date(2027, 1, 5))
        assert tr.start == date(2026, 12, 31)
        assert tr.end == date(2026, 12, 31)

    def test_month_day_past_stays_current_year(self):
        """'3月1日' queried on March 13 should stay current year."""
        tr = extract_time_range("3月1日的数据", today=date(2027, 3, 13))
        assert tr.start == date(2027, 3, 1)

    def test_month_day_today_stays_current_year(self):
        """Same day as today should stay current year."""
        tr = extract_time_range("6月15日的数据", today=date(2027, 6, 15))
        assert tr.start == date(2027, 6, 15)


# ------------------------------------------------------------------
# Token truncation
# ------------------------------------------------------------------

class TestTokenTruncation:
    def test_short_conversation_unchanged(self):
        from seatunnel_agent.context import truncate_messages
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = truncate_messages(msgs, max_chars=10000)
        assert len(result) == 2

    def test_long_conversation_trimmed(self):
        from seatunnel_agent.context import truncate_messages
        msgs = [{"role": "user", "content": "x" * 5000} for _ in range(50)]
        result = truncate_messages(msgs, max_chars=20000)
        total_chars = sum(len(m.get("content", "")) for m in result)
        assert total_chars <= 25000  # some slack for the marker message
        assert len(result) < 50

    def test_truncation_adds_marker(self):
        from seatunnel_agent.context import truncate_messages
        msgs = [
            {"role": "user", "content": "a" * 5000},
            {"role": "assistant", "content": "b" * 5000},
            {"role": "user", "content": "c" * 5000},
            {"role": "assistant", "content": "d" * 5000},
            {"role": "user", "content": "e" * 5000},
        ]
        result = truncate_messages(msgs, max_chars=12000)
        assert result[0]["role"] == "user"
        assert len(result) < len(msgs)

    def test_empty_messages_unchanged(self):
        from seatunnel_agent.context import truncate_messages
        assert truncate_messages([]) == []


# ------------------------------------------------------------------
# Executor: cursor close and table name validation
# ------------------------------------------------------------------

class TestExecutorSafety:
    def test_invalid_table_name_rejected(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="default")
        executor = HiveExecutor(config)
        with pytest.raises(ValueError, match="Invalid table name"):
            executor.get_max_partition("DROP TABLE foo; --")

    def test_valid_table_name_format(self):
        from seatunnel_agent.text2sql.executor.base import _TABLE_NAME_RE
        assert _TABLE_NAME_RE.fullmatch("db.table_name")
        assert _TABLE_NAME_RE.fullmatch("cladata.student")
        assert not _TABLE_NAME_RE.fullmatch("DROP TABLE foo")
        assert not _TABLE_NAME_RE.fullmatch("db.table; DROP")

    def test_cursor_closed_on_success(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="default")
        executor = HiveExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",)]
        mock_cursor.fetchmany.return_value = [(1,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            executor.run("SELECT 1")
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_cursor_closed_on_error(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="default")
        executor = HiveExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("boom")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            with pytest.raises(RuntimeError):
                executor.run("SELECT fail")
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


# ------------------------------------------------------------------
# Test connection
# ------------------------------------------------------------------

class TestHiveConnection:
    def test_connection_success(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="test")
        executor = HiveExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            ok, msg = executor.test_connection()
        assert ok is True
        assert "localhost" in msg

    def test_connection_failure(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="badhost", port=10000, database="default")
        executor = HiveExecutor(config)
        with patch.object(executor, "_connect", side_effect=ConnectionError("refused")):
            ok, msg = executor.test_connection()
        assert ok is False
        assert "refused" in msg


# ------------------------------------------------------------------
# Hive schema introspection
# ------------------------------------------------------------------

class TestHiveSchemaFetch:
    def test_show_tables(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="testdb")
        executor = HiveExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table_a",), ("table_b",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            tables = executor.show_tables()
        assert tables == ["table_a", "table_b"]
        mock_cursor.close.assert_called_once()

    def test_describe_table(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="testdb")
        executor = HiveExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "bigint", "primary key"),
            ("name", "string", "user name"),
            ("", "", ""),
            ("# Partition Information", "", ""),
            ("# col_name", "data_type", "comment"),
            ("pt", "string", "partition date"),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            schema = executor.describe_table("users")
        assert schema.database == "testdb"
        assert schema.name == "users"
        assert len(schema.columns) == 2
        assert schema.columns[0].name == "id"
        assert schema.columns[1].name == "name"
        assert len(schema.partition_columns) == 1
        assert schema.partition_columns[0].name == "pt"
        mock_cursor.close.assert_called_once()

    def test_from_db(self):
        from seatunnel_agent.text2sql.executor import HiveExecutor, DatabaseConfig
        from seatunnel_agent.text2sql.schema import SchemaStore, TableSchema, ColumnSchema
        config = DatabaseConfig(ds_type="hive", host="localhost", port=10000, database="testdb")
        executor = HiveExecutor(config)
        fake_tables = [
            TableSchema(database="testdb", name="t1",
                        columns=[ColumnSchema("c1", "string")]),
            TableSchema(database="testdb", name="t2",
                        columns=[ColumnSchema("c2", "int")]),
        ]
        with patch.object(executor, "fetch_all_schemas", return_value=fake_tables):
            store = SchemaStore.from_db(executor)
        assert len(store) == 2
        assert store.get("testdb.t1") is not None
        assert store.get("testdb.t2") is not None


# ------------------------------------------------------------------
# QueryLogger rotation
# ------------------------------------------------------------------

class TestLogRotation:
    def test_rotate_on_large_file(self, tmp_path):
        logger = QueryLogger(log_dir=str(tmp_path))
        logger.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.log_file.write_text("x" * (11 * 1024 * 1024))
        logger.log("q", "sql", "ok")
        assert (tmp_path / "text2sql_queries.1.jsonl").exists()
        assert logger.log_file.stat().st_size < 1000


# ------------------------------------------------------------------
# QueryLogger delete
# ------------------------------------------------------------------

class TestLogDelete:
    def _make_logger(self, tmp_path, n=5):
        logger = QueryLogger(log_dir=str(tmp_path))
        for i in range(n):
            logger.log(f"q{i}", f"SELECT {i}", "success")
        return logger

    def test_delete_newest(self, tmp_path):
        logger = self._make_logger(tmp_path, 5)
        deleted = logger.delete([0])  # newest = q4
        assert deleted == 1
        recs = logger.recent(10)
        assert len(recs) == 4
        assert recs[-1]["user_query"] == "q3"

    def test_delete_multiple(self, tmp_path):
        logger = self._make_logger(tmp_path, 5)
        deleted = logger.delete([0, 2, 4])  # q4, q2, q0
        assert deleted == 3
        recs = logger.recent(10)
        assert [r["user_query"] for r in recs] == ["q1", "q3"]

    def test_delete_out_of_range_ignored(self, tmp_path):
        logger = self._make_logger(tmp_path, 3)
        deleted = logger.delete([0, 10, 99])
        assert deleted == 1
        assert len(logger.recent(10)) == 2

    def test_delete_empty_list(self, tmp_path):
        logger = self._make_logger(tmp_path, 3)
        deleted = logger.delete([])
        assert deleted == 0
        assert len(logger.recent(10)) == 3

    def test_delete_no_file(self, tmp_path):
        logger = QueryLogger(log_dir=str(tmp_path))
        assert logger.delete([0]) == 0


# ------------------------------------------------------------------
# Chart detection (chart.py)
# ------------------------------------------------------------------

class TestChartDetection:
    def test_detect_bar(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["city", "sales"]
        rows = [("Beijing", 100), ("Shanghai", 200), ("Guangzhou", 150)]
        assert detect_chart_type(cols, rows) == "pie"  # <=8 categories + 1 numeric

    def test_detect_bar_many_rows(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["city", "sales"]
        rows = [(f"city_{i}", i * 10) for i in range(20)]
        assert detect_chart_type(cols, rows) == "bar"

    def test_detect_line(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["date", "amount"]
        rows = [("2026-01-01", 10), ("2026-01-02", 20), ("2026-01-03", 30)]
        assert detect_chart_type(cols, rows) == "line"

    def test_detect_pie(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["category", "count"]
        rows = [("A", 10), ("B", 20), ("C", 30)]
        assert detect_chart_type(cols, rows) == "pie"

    def test_detect_none_too_few_rows(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        assert detect_chart_type(["a", "b"], [(1, 2)]) is None

    def test_detect_none_no_numeric(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["name", "city"]
        rows = [("Alice", "BJ"), ("Bob", "SH"), ("Carol", "GZ")]
        assert detect_chart_type(cols, rows) is None

    def test_build_chart_bar(self):
        from seatunnel_agent.text2sql.chart import build_chart
        import matplotlib.pyplot as plt
        cols = ["city", "sales"]
        rows = [(f"city_{i}", i * 10) for i in range(10)]
        fig = build_chart(cols, rows, "bar")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_build_chart_empty(self):
        from seatunnel_agent.text2sql.chart import build_chart
        assert build_chart([], [], "bar") is None


# ------------------------------------------------------------------
# Favorites store (favorites.py)
# ------------------------------------------------------------------

class TestFavoritesStore:
    def test_empty_store(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(path=tmp_path / "favs.json")
        assert store.list() == []

    def test_save_and_list(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(path=tmp_path / "favs.json")
        entry = store.save(name="test", sql="SELECT 1", question="q", ds_type="mysql")
        assert entry["name"] == "test"
        assert entry["sql"] == "SELECT 1"
        items = store.list()
        assert len(items) == 1
        assert items[0]["id"] == entry["id"]

    def test_delete(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(path=tmp_path / "favs.json")
        entry = store.save(name="del", sql="SELECT 2")
        assert store.delete(entry["id"]) is True
        assert store.list() == []

    def test_delete_nonexistent(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(path=tmp_path / "favs.json")
        assert store.delete("nonexistent") is False

    def test_multiple_entries(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(path=tmp_path / "favs.json")
        for i in range(3):
            store.save(name=f"q{i}", sql=f"SELECT {i}")
        assert len(store.list()) == 3


# ------------------------------------------------------------------
# MySQL executor (mock level)
# ------------------------------------------------------------------

class TestMySQLExecutor:
    def test_run_query(self):
        from seatunnel_agent.text2sql.executor.mysql import MySQLExecutor
        config = DatabaseConfig(ds_type="mysql", host="localhost", port=3306, database="testdb",
                                username="root", password="")
        executor = MySQLExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchmany.return_value = [(1, "Alice"), (2, "Bob")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            result = executor.run("SELECT id, name FROM users")
        assert result.columns == ["id", "name"]
        assert result.row_count == 2
        mock_cursor.close.assert_called_once()

    def test_show_tables(self):
        from seatunnel_agent.text2sql.executor.mysql import MySQLExecutor
        config = DatabaseConfig(ds_type="mysql", host="localhost", port=3306, database="testdb")
        executor = MySQLExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users",), ("orders",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            tables = executor.show_tables()
        assert tables == ["users", "orders"]

    def test_describe_table(self):
        from seatunnel_agent.text2sql.executor.mysql import MySQLExecutor
        config = DatabaseConfig(ds_type="mysql", host="localhost", port=3306, database="testdb")
        executor = MySQLExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "bigint", "primary key"),
            ("name", "varchar(100)", "user name"),
        ]
        mock_cursor.fetchone.return_value = ("用户表",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            schema = executor.describe_table("users")
        assert schema.name == "users"
        assert len(schema.columns) == 2
        assert schema.comment == "用户表"

    def test_connection_success(self):
        from seatunnel_agent.text2sql.executor.mysql import MySQLExecutor
        config = DatabaseConfig(ds_type="mysql", host="localhost", port=3306, database="testdb")
        executor = MySQLExecutor(config)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch.object(executor, "_connect", return_value=mock_conn):
            ok, msg = executor.test_connection()
        assert ok is True

    def test_connection_failure(self):
        from seatunnel_agent.text2sql.executor.mysql import MySQLExecutor
        config = DatabaseConfig(ds_type="mysql", host="badhost", port=3306, database="testdb")
        executor = MySQLExecutor(config)
        with patch.object(executor, "_connect", side_effect=ConnectionError("refused")):
            ok, msg = executor.test_connection()
        assert ok is False


# ------------------------------------------------------------------
# Validator: set/add false positive fix
# ------------------------------------------------------------------

class TestValidatorSetAdd:
    def test_set_in_column_name_ok(self, store):
        r = validate_sql("SELECT * FROM atest.student WHERE name = 'data_set'", store)
        assert r.ok, r.errors

    def test_add_in_column_name_ok(self, store):
        r = validate_sql("SELECT id FROM atest.student WHERE name = 'address'", store)
        assert r.ok, r.errors

    def test_set_statement_rejected(self, store):
        r = validate_sql("SET mapreduce.framework = yarn", store)
        assert not r.ok

    def test_add_jar_rejected(self, store):
        r = validate_sql("ADD JAR /tmp/udf.jar", store)
        assert not r.ok
