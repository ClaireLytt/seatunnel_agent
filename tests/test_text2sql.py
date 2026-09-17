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


# ------------------------------------------------------------------
# Bug fix regressions: enforce_limit edge cases
# ------------------------------------------------------------------

class TestEnforceLimitEdgeCases:
    def test_limit_with_offset_preserved(self):
        sql = "SELECT * FROM t LIMIT 50 OFFSET 10"
        result = enforce_limit(sql)
        assert "LIMIT 50" in result
        assert "OFFSET 10" in result
        assert result.count("LIMIT") == 1

    def test_limit_with_offset_capped(self):
        sql = "SELECT * FROM t LIMIT 999999 OFFSET 10"
        result = enforce_limit(sql, max_limit=100000)
        assert "LIMIT 100000" in result
        assert "OFFSET 10" in result

    def test_sqlserver_cte_gets_top(self):
        sql = "WITH cte AS (SELECT id FROM t) SELECT * FROM cte"
        result = enforce_limit(sql, dialect="sqlserver")
        assert "TOP 1000" in result
        assert result.index("TOP") > result.index("cte AS")

    def test_sqlserver_plain_select_gets_top(self):
        sql = "SELECT * FROM users"
        result = enforce_limit(sql, dialect="sqlserver")
        assert "TOP 1000" in result

    def test_build_chart_no_numeric_returns_none(self):
        from seatunnel_agent.text2sql.chart import build_chart
        cols = ["name", "city"]
        rows = [("Alice", "BJ"), ("Bob", "SH")]
        assert build_chart(cols, rows, "bar") is None


# ------------------------------------------------------------------
# Bug audit fixes
# ------------------------------------------------------------------

class TestTokenRegexDigitSplit:
    """Bug fix: r'[a-zA-Z_]+' split on digits → false positive on columns
    like export2024. Changed to r'[a-zA-Z_]\\w*' to keep full identifiers."""

    def test_column_export2024_allowed(self, store):
        r = validate_sql("SELECT export2024 FROM atest.student", store)
        assert "export" not in [e.lower() for e in r.errors if "Forbidden" in e], r.errors

    def test_column_analyze3_allowed(self, store):
        r = validate_sql("SELECT analyze3 FROM atest.student", store)
        assert r.ok or all("Forbidden" not in e for e in r.errors), r.errors

    def test_real_export_keyword_still_blocked(self, store):
        r = validate_sql("EXPORT TABLE atest.student TO '/tmp'", store)
        assert not r.ok


class TestDoubleQuotedIdentifiers:
    """Bug fix: double-quoted identifiers were stripped as string literals,
    causing extract_tables to miss PostgreSQL-style FROM \"table\"."""

    def test_extract_double_quoted_table(self):
        tables = extract_tables('SELECT * FROM "my_table"')
        assert "my_table" in tables

    def test_extract_double_quoted_with_schema(self):
        tables = extract_tables('SELECT * FROM "mydb"."my_table"')
        assert "mydb.my_table" in tables

    def test_validate_double_quoted_not_in_whitelist(self, store):
        r = validate_sql('SELECT * FROM "not_whitelisted"', store)
        assert not r.ok
        assert any("not_whitelisted" in e for e in r.errors)


class TestPieChartNegativeValues:
    """Bug fix: pie chart should not be returned when values contain negatives."""

    def test_negative_values_not_pie(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["category", "profit"]
        rows = [("A", 100), ("B", -50), ("C", 200)]
        ct = detect_chart_type(cols, rows)
        assert ct != "pie"

    def test_positive_values_still_pie(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        cols = ["category", "count"]
        rows = [("A", 10), ("B", 20), ("C", 30)]
        ct = detect_chart_type(cols, rows)
        assert ct == "pie"


class TestScatterChart:
    """Feature 4: scatter chart type."""

    def test_scatter_with_two_numeric(self):
        from seatunnel_agent.text2sql.chart import build_chart
        import matplotlib.pyplot as plt
        cols = ["x", "y"]
        rows = [(1, 10), (2, 20), (3, 15), (4, 25)]
        fig = build_chart(cols, rows, "scatter")
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_scatter_with_one_numeric(self):
        from seatunnel_agent.text2sql.chart import build_chart
        import matplotlib.pyplot as plt
        cols = ["name", "value"]
        rows = [("A", 10), ("B", 20), ("C", 30)]
        fig = build_chart(cols, rows, "scatter")
        assert fig is not None
        plt.close(fig)


class TestEnvPrefixFlink:
    """Bug fix: flinksql was missing from _ENV_PREFIX."""

    def test_flinksql_prefix_exists(self):
        from seatunnel_agent.text2sql.executor.base import _ENV_PREFIX
        assert "flinksql" in _ENV_PREFIX

    def test_config_from_env_flinksql(self, monkeypatch):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        monkeypatch.setenv("FLINK_HOST", "flink-host")
        monkeypatch.setenv("FLINK_PORT", "8083")
        cfg = config_from_env("flinksql")
        assert cfg is not None
        assert cfg.host == "flink-host"


class TestLogRotationSuffix:
    """Bug fix: with_suffix('.1.jsonl') dropped .jsonl → now uses with_name."""

    def test_rotated_filename(self, tmp_path):
        from seatunnel_agent.text2sql.qlog import QueryLogger
        logger = QueryLogger(log_dir=str(tmp_path))
        logger._MAX_LOG_BYTES = 10
        logger.log(user_query="q" * 50, generated_sql="s", status="ok")
        logger.log(user_query="q2", generated_sql="s2", status="ok")
        rotated = tmp_path / "text2sql_queries.1.jsonl"
        assert rotated.exists(), f"Expected {rotated}, got {list(tmp_path.iterdir())}"


class TestSqlServerCteWithComment:
    """Bug fix: comment between ) and outer SELECT broke CTE TOP injection."""

    def test_cte_comment_before_select(self):
        sql = (
            "WITH cte AS (SELECT id FROM t)\n"
            "-- get results\n"
            "SELECT * FROM cte"
        )
        result = enforce_limit(sql, default_limit=100, dialect="sqlserver")
        assert "TOP 100" in result
        assert "SELECT id FROM t" in result or "SELECT id" in result
        assert result.index("TOP 100") > result.index("AS")


# ------------------------------------------------------------------
# SQL auto-fix: error classification and retry tracking
# ------------------------------------------------------------------

class TestErrorClassification:
    """Test classify_error() returns correct (error_type, retry_hint)."""

    def test_column_not_found(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("cannot resolve 'col_x' given columns")
        assert etype == "column_not_found"
        assert "get_table_schema" in hint

    def test_unknown_column(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, _ = classify_error("Unknown column 'abc' in 'field list'")
        assert etype == "column_not_found"

    def test_syntax_error(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("syntax error at or near 'SELEC'")
        assert etype == "syntax_error"
        assert "syntax" in hint.lower()

    def test_parse_error(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, _ = classify_error("mismatched input 'FROM' expecting {<EOF>}")
        assert etype == "syntax_error"

    def test_line_col_error(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, _ = classify_error("line 1:42 cannot recognize input")
        assert etype == "syntax_error"

    def test_type_mismatch(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("data type mismatch: cannot cast string to int")
        assert etype == "type_mismatch"
        assert "CAST" in hint

    def test_conversion_failed(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, _ = classify_error("conversion failed when converting varchar to numeric")
        assert etype == "type_mismatch"

    def test_fallback(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, _ = classify_error("connection timed out")
        assert etype == "execution_error"


class TestRetryTracking:
    """Test sql_retries counter and max_retries_reached flag."""

    def test_retries_increment_on_error(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        rt = Text2SQLRuntime(store=store, ds_type="hive")
        result = _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        assert result.get("attempt") == 1
        assert result.get("error_type") is not None
        result2 = _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        assert result2.get("attempt") == 2

    def test_retries_reset_on_success(self, store, monkeypatch):
        from unittest.mock import MagicMock
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.sql_retries = 2
        mock_executor = MagicMock()
        mock_executor.run.return_value = QueryResult(
            columns=["id"], rows=[(1,)], row_count=1,
            truncated=False, elapsed_ms=10,
        )
        rt._executor = mock_executor
        result = _tool_execute_sql(
            {"sql": "SELECT id FROM atest.student"}, rt,
        )
        assert result.get("success") is True
        assert rt.sql_retries == 0

    def test_max_retries_reached(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        rt = Text2SQLRuntime(store=store, ds_type="hive", max_sql_retries=2)
        _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        result = _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        assert result.get("max_retries_reached") is True
        assert result.get("attempt") == 2

    def test_error_has_retry_hint(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        rt = Text2SQLRuntime(store=store, ds_type="hive")
        result = _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        assert "retry_hint" in result
        assert len(result["retry_hint"]) > 0


class TestSqlResultCache:
    """Unit tests for SqlResultCache."""

    def test_cache_hit(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache(ttl_seconds=60)
        qr = QueryResult(columns=["a"], rows=[(1,)], row_count=1, truncated=False, elapsed_ms=5)
        cache.put("SELECT a FROM t", "hive", qr)
        assert cache.get("SELECT a FROM t", "hive") is qr

    def test_cache_miss(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        cache = SqlResultCache()
        assert cache.get("SELECT 1", "hive") is None

    def test_cache_ttl_expiry(self, monkeypatch):
        import time as _time
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache(ttl_seconds=1)
        qr = QueryResult(columns=["x"], rows=[], row_count=0, truncated=False, elapsed_ms=0)
        cache.put("SELECT x FROM t", "mysql", qr)
        assert cache.get("SELECT x FROM t", "mysql") is qr
        original_mono = _time.monotonic
        monkeypatch.setattr(_time, "monotonic", lambda: original_mono() + 2)
        assert cache.get("SELECT x FROM t", "mysql") is None

    def test_cache_normalization(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache()
        qr = QueryResult(columns=["a"], rows=[(1,)], row_count=1, truncated=False, elapsed_ms=5)
        cache.put("SELECT  a  FROM  t", "hive", qr)
        assert cache.get("select a from t", "hive") is qr
        assert cache.get("  SELECT   A   FROM   T  ", "hive") is qr

    def test_cache_invalidate(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache()
        qr = QueryResult(columns=["a"], rows=[], row_count=0, truncated=False, elapsed_ms=0)
        cache.put("SELECT 1", "hive", qr)
        cache.put("SELECT 2", "mysql", qr)
        assert cache.stats["size"] == 2
        cache.invalidate()
        assert cache.stats["size"] == 0
        assert cache.get("SELECT 1", "hive") is None

    def test_cache_max_entries(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache(max_entries=3)
        for i in range(5):
            qr = QueryResult(columns=[f"c{i}"], rows=[], row_count=0, truncated=False, elapsed_ms=0)
            cache.put(f"SELECT {i}", "hive", qr)
        assert cache.stats["size"] == 3

    def test_cache_stats(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache()
        qr = QueryResult(columns=["a"], rows=[], row_count=0, truncated=False, elapsed_ms=0)
        cache.put("SELECT 1", "hive", qr)
        cache.get("SELECT 1", "hive")
        cache.get("SELECT 1", "hive")
        cache.get("SELECT 999", "hive")
        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_ds_type_isolation(self):
        from seatunnel_agent.text2sql.cache import SqlResultCache
        from seatunnel_agent.text2sql.executor import QueryResult
        cache = SqlResultCache()
        qr = QueryResult(columns=["a"], rows=[(1,)], row_count=1, truncated=False, elapsed_ms=5)
        cache.put("SELECT a FROM t", "hive", qr)
        assert cache.get("SELECT a FROM t", "hive") is qr
        assert cache.get("SELECT a FROM t", "mysql") is None


class TestCacheIntegration:
    """Integration: _tool_execute_sql uses the cache."""

    def test_execute_sql_cache_hit(self, store):
        from unittest.mock import MagicMock
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        mock_executor = MagicMock()
        mock_executor.run.return_value = QueryResult(
            columns=["id"], rows=[(1,)], row_count=1,
            truncated=False, elapsed_ms=10,
        )
        rt._executor = mock_executor
        r1 = _tool_execute_sql({"sql": "SELECT id FROM atest.student"}, rt)
        assert r1.get("success") is True
        assert r1.get("cached") is None
        assert mock_executor.run.call_count == 1
        r2 = _tool_execute_sql({"sql": "SELECT id FROM atest.student"}, rt)
        assert r2.get("success") is True
        assert r2.get("cached") is True
        assert r2.get("elapsed_ms") == 0
        assert mock_executor.run.call_count == 1

    def test_execute_sql_error_not_cached(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_execute_sql
        rt = Text2SQLRuntime(store=store, ds_type="hive")
        r1 = _tool_execute_sql({"sql": "DROP TABLE t"}, rt)
        assert r1.get("error") is not None
        assert rt.cache.stats["size"] == 0


class TestChatHistory:
    """Feature 7: chat history persistence."""

    def test_save_and_load(self, tmp_path, monkeypatch):
        import seatunnel_agent.text2sql.chat_history as ch
        monkeypatch.setattr(ch, "HISTORY_DIR", tmp_path)
        session = ch.Text2SQLSession(
            session_id="abc123",
            title="Test",
            created_at=ch.now_iso(),
            updated_at=ch.now_iso(),
            ds_type="mysql",
            chat_messages=[{"role": "user", "content": "hello"}],
        )
        ch.save_t2s_session(session)
        loaded = ch.load_t2s_session("abc123")
        assert loaded is not None
        assert loaded.title == "Test"
        assert len(loaded.chat_messages) == 1

    def test_list_sessions(self, tmp_path, monkeypatch):
        import seatunnel_agent.text2sql.chat_history as ch
        monkeypatch.setattr(ch, "HISTORY_DIR", tmp_path)
        for i in range(3):
            s = ch.Text2SQLSession(
                session_id=f"s{i}",
                title=f"Session {i}",
                created_at=ch.now_iso(),
                updated_at=ch.now_iso(),
            )
            ch.save_t2s_session(s)
        sessions = ch.list_t2s_sessions()
        assert len(sessions) == 3

    def test_delete_session(self, tmp_path, monkeypatch):
        import seatunnel_agent.text2sql.chat_history as ch
        monkeypatch.setattr(ch, "HISTORY_DIR", tmp_path)
        s = ch.Text2SQLSession(
            session_id="del1",
            title="To Delete",
            created_at=ch.now_iso(),
            updated_at=ch.now_iso(),
        )
        ch.save_t2s_session(s)
        assert ch.load_t2s_session("del1") is not None
        ch.delete_t2s_session("del1")
        assert ch.load_t2s_session("del1") is None

    def test_extract_title(self):
        from seatunnel_agent.text2sql.chat_history import extract_title
        msgs = [{"role": "user", "content": "查询最近的销售数据"}]
        assert extract_title(msgs) == "查询最近的销售数据"
        assert extract_title([]) == "Untitled"

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        import seatunnel_agent.text2sql.chat_history as ch
        monkeypatch.setattr(ch, "HISTORY_DIR", tmp_path)
        assert ch.load_t2s_session("nonexistent") is None


class TestGetResultPage:
    """Feature 6: pagination tool."""

    def test_basic_page(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_get_result_page
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.last_result = QueryResult(
            columns=["id"], rows=[(i,) for i in range(120)],
            row_count=120, truncated=False, elapsed_ms=10,
        )
        result = _tool_get_result_page({"page": 1, "page_size": 50}, rt)
        assert result["success"] is True
        assert len(result["rows"]) == 50
        assert result["page"] == 1
        assert result["total_pages"] == 3
        assert result["total_rows"] == 120

    def test_last_page(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_get_result_page
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.last_result = QueryResult(
            columns=["id"], rows=[(i,) for i in range(120)],
            row_count=120, truncated=False, elapsed_ms=10,
        )
        result = _tool_get_result_page({"page": 3, "page_size": 50}, rt)
        assert result["success"] is True
        assert len(result["rows"]) == 20
        assert result["page"] == 3

    def test_page_beyond_max_clamped(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_get_result_page
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.last_result = QueryResult(
            columns=["id"], rows=[(1,), (2,)],
            row_count=2, truncated=False, elapsed_ms=10,
        )
        result = _tool_get_result_page({"page": 999}, rt)
        assert result["page"] == 1

    def test_no_result(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_get_result_page
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        result = _tool_get_result_page({"page": 1}, rt)
        assert result.get("error") is not None


class TestExportExcelPdf:
    """Feature 5: Excel and PDF export."""

    def test_export_excel(self, tmp_path):
        from seatunnel_agent.text2sql.exporter import export_excel
        cols = ["name", "score"]
        rows = [("Alice", 90), ("Bob", 85)]
        path = export_excel(cols, rows, path=str(tmp_path), name_hint="test")
        assert path.endswith(".xlsx")
        assert Path(path).is_file()
        from openpyxl import load_workbook
        wb = load_workbook(path)
        ws = wb.active
        assert ws.cell(1, 1).value == "name"
        assert ws.cell(2, 1).value == "Alice"
        assert ws.freeze_panes == "A2"

    def test_export_pdf(self, tmp_path):
        from seatunnel_agent.text2sql.exporter import export_pdf
        cols = ["name", "score"]
        rows = [("Alice", 90), ("Bob", 85)]
        path = export_pdf(cols, rows, path=str(tmp_path), name_hint="test")
        assert path.endswith(".pdf")
        assert Path(path).is_file()
        assert Path(path).stat().st_size > 100

    def test_export_excel_tool(self, store, tmp_path):
        from unittest.mock import MagicMock
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_export_excel
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.last_result = QueryResult(
            columns=["id", "name"], rows=[(1, "A"), (2, "B")],
            row_count=2, truncated=False, elapsed_ms=10,
        )
        result = _tool_export_excel({"path": str(tmp_path)}, rt)
        assert result["success"] is True
        assert result["excel_path"].endswith(".xlsx")

    def test_export_pdf_tool(self, store, tmp_path):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_export_pdf
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        rt.last_result = QueryResult(
            columns=["id", "name"], rows=[(1, "A"), (2, "B")],
            row_count=2, truncated=False, elapsed_ms=10,
        )
        result = _tool_export_pdf({"path": str(tmp_path), "title": "Test Report"}, rt)
        assert result["success"] is True
        assert result["pdf_path"].endswith(".pdf")

    def test_export_no_result(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_export_excel, _tool_export_pdf
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        assert _tool_export_excel({}, rt).get("error") is not None
        assert _tool_export_pdf({}, rt).get("error") is not None


class TestExplainSql:
    """Tests for the explain_sql tool."""

    def test_explain_success(self, store):
        from unittest.mock import MagicMock
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_explain_sql
        from seatunnel_agent.text2sql.executor import QueryResult
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        mock_executor = MagicMock()
        mock_executor.run.return_value = QueryResult(
            columns=["id", "select_type", "table"],
            rows=[("1", "SIMPLE", "student")],
            row_count=1, truncated=False, elapsed_ms=5,
        )
        rt._executor = mock_executor
        result = _tool_explain_sql({"sql": "SELECT id FROM atest.student"}, rt)
        assert result["success"] is True
        assert "SIMPLE" in result["plan"]
        mock_executor.run.assert_called_once()
        call_sql = mock_executor.run.call_args[0][0]
        assert call_sql.startswith("EXPLAIN ")

    def test_explain_unsupported_engine(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_explain_sql
        rt = Text2SQLRuntime(store=store, ds_type="sqlserver")
        result = _tool_explain_sql({"sql": "SELECT 1"}, rt)
        assert "not supported" in result["error"]

    def test_explain_rejects_non_select(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_explain_sql
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        result = _tool_explain_sql({"sql": "DROP TABLE atest.student"}, rt)
        assert result.get("error") is not None

    def test_explain_empty_sql(self, store):
        from seatunnel_agent.text2sql.tools import Text2SQLRuntime, _tool_explain_sql
        rt = Text2SQLRuntime(store=store, ds_type="mysql")
        result = _tool_explain_sql({"sql": ""}, rt)
        assert result.get("error") is not None


class TestSqlTemplates:
    """Feature 8: SQL template library."""

    def test_all_templates_have_required_keys(self):
        from seatunnel_agent.text2sql.templates import SQL_TEMPLATES
        required = {"id", "name_en", "name_zh", "description_en", "description_zh", "pattern"}
        for t in SQL_TEMPLATES:
            assert required <= set(t.keys()), f"Template {t.get('id')} missing keys"

    def test_template_count(self):
        from seatunnel_agent.text2sql.templates import SQL_TEMPLATES
        assert len(SQL_TEMPLATES) == 8

    def test_get_template(self):
        from seatunnel_agent.text2sql.templates import get_template
        t = get_template("topn")
        assert t is not None
        assert t["id"] == "topn"
        assert "LIMIT" in t["pattern"]
        assert get_template("nonexistent") is None

    def test_template_choices_en(self):
        from seatunnel_agent.text2sql.templates import template_choices
        choices = template_choices("en")
        assert len(choices) == 8
        assert any("Top N" in c for c in choices)
        assert all("[" in c and "]" in c for c in choices)

    def test_template_choices_zh(self):
        from seatunnel_agent.text2sql.templates import template_choices
        choices = template_choices("zh")
        assert any("排行" in c for c in choices)

    def test_template_description(self):
        from seatunnel_agent.text2sql.templates import template_description
        desc = template_description("mom", "en")
        assert "Compare" in desc
        assert "```sql" in desc
        desc_zh = template_description("mom", "zh")
        assert "对比" in desc_zh
        assert template_description("nonexistent") == ""


class TestRestApi:
    """Feature 10: REST API endpoints."""

    def test_health(self):
        from fastapi.testclient import TestClient
        from seatunnel_agent.text2sql.api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/text2sql/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_schema_endpoint(self):
        from fastapi.testclient import TestClient
        from seatunnel_agent.text2sql.api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/text2sql/schema")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_query_no_config(self):
        from fastapi.testclient import TestClient
        from seatunnel_agent.text2sql.api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/api/text2sql/query", json={
            "question": "show all students",
            "ds_type": "hive",
        })
        assert resp.status_code == 400

    def test_query_with_ddl(self, monkeypatch):
        from fastapi.testclient import TestClient
        from seatunnel_agent.text2sql.api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_agent = MagicMock()
        mock_agent.messages = []
        mock_agent.run.return_value = "The answer is 42"
        mock_rt = MagicMock()
        mock_rt.last_sql = "SELECT 1"
        mock_rt.last_result = QueryResult(
            columns=["id"], rows=[(1,)], row_count=1,
            truncated=False, elapsed_ms=5,
        )
        mock_agent.runtime = mock_rt

        import seatunnel_agent.text2sql.api as api_mod
        monkeypatch.setattr(api_mod, "_build_agent", lambda *a, **kw: mock_agent)

        resp = client.post("/api/text2sql/query", json={
            "question": "show all students",
            "ds_type": "hive",
            "schema_ddl": _DDL,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "The answer is 42"
        assert data["sql"] == "SELECT 1"
        assert data["row_count"] == 1


class TestSchemaBrowser:
    """Tests for the schema browser card builder (Direction 11)."""

    def _make_table(self, name="test_db.users", comment="User table",
                    columns=None, partition_columns=None):
        from seatunnel_agent.text2sql.schema import ColumnSchema, TableSchema
        if columns is None:
            columns = [
                ColumnSchema(name="id", dtype="bigint", comment="Primary key"),
                ColumnSchema(name="name", dtype="string", comment="User name"),
            ]
        if partition_columns is None:
            partition_columns = []
        db, tbl = name.split(".", 1) if "." in name else ("", name)
        return TableSchema(
            database=db, name=tbl, comment=comment,
            columns=columns, partition_columns=partition_columns,
        )

    def test_basic_card(self):
        from seatunnel_agent.text2sql_ui import build_schema_card
        table = self._make_table()
        html = build_schema_card(table)
        assert "test_db.users" in html
        assert "User table" in html
        assert "bigint" in html
        assert "id" in html
        assert "name" in html
        assert "Primary key" in html
        assert "2 columns" in html

    def test_partitioned_card(self):
        from seatunnel_agent.text2sql_ui import build_schema_card
        from seatunnel_agent.text2sql.schema import ColumnSchema
        table = self._make_table(
            partition_columns=[
                ColumnSchema(name="dt", dtype="string", comment="Date partition"),
            ],
        )
        html = build_schema_card(table)
        assert "partitioned" in html
        assert "dt" in html
        assert "Date partition" in html
        assert "Partition Columns" in html
        assert "3 columns" in html

    def test_empty_comment(self):
        from seatunnel_agent.text2sql_ui import build_schema_card
        table = self._make_table(comment="")
        html = build_schema_card(table)
        assert "test_db.users" in html
        assert "bigint" in html

    def test_zh_labels(self):
        from seatunnel_agent.text2sql_ui import build_schema_card
        table = self._make_table()
        html = build_schema_card(table, lang="zh")
        assert "test_db.users" in html
        assert "2 个字段" in html
        assert "字段列表" in html

    def test_xss_escape(self):
        from seatunnel_agent.text2sql_ui import build_schema_card
        from seatunnel_agent.text2sql.schema import ColumnSchema
        table = self._make_table(
            comment="<script>alert(1)</script>",
            columns=[ColumnSchema(name="x", dtype="string", comment="a&b")],
        )
        html = build_schema_card(table)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "a&amp;b" in html


class TestDataLineage:
    """Tests for SQL data lineage extraction (Direction 12)."""

    def test_simple_select(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "SELECT id, name FROM users"
        lineage = trace_lineage(sql)
        assert lineage.source_tables == ["users"]
        assert len(lineage.output_columns) == 2
        names = [c.output_name for c in lineage.output_columns]
        assert "id" in names
        assert "name" in names

    def test_join_lineage(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = (
            "SELECT o.id, c.name "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "WHERE o.status = 'active'"
        )
        lineage = trace_lineage(sql)
        assert "orders" in lineage.source_tables
        assert "customers" in lineage.source_tables
        assert len(lineage.joins) >= 1
        assert any("customer_id" in j for j in lineage.joins)
        assert len(lineage.filters) >= 1

    def test_multi_condition_join(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = (
            "SELECT o.id, c.name "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id AND o.region = c.region"
        )
        lineage = trace_lineage(sql)
        assert len(lineage.joins) == 2
        assert any("customer_id" in j for j in lineage.joins)
        assert any("region" in j for j in lineage.joins)

    def test_aggregation(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "SELECT city, SUM(amount) AS total FROM orders GROUP BY city"
        lineage = trace_lineage(sql)
        assert lineage.source_tables == ["orders"]
        agg_cols = [c for c in lineage.output_columns if c.is_aggregation]
        assert len(agg_cols) >= 1
        assert agg_cols[0].output_name == "total"
        assert lineage.group_by

    def test_where_filter(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "SELECT id FROM users WHERE age > 18 AND status = 'active'"
        lineage = trace_lineage(sql)
        assert len(lineage.filters) >= 2

    def test_group_by(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "SELECT dept, COUNT(*) AS cnt FROM emp GROUP BY dept"
        lineage = trace_lineage(sql)
        assert "dept" in lineage.group_by

    def test_cte_excluded(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "WITH tmp AS (SELECT id FROM users) SELECT * FROM tmp"
        lineage = trace_lineage(sql)
        assert "tmp" not in lineage.source_tables
        assert "tmp" in lineage.cte_names

    def test_star_select(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        sql = "SELECT * FROM orders"
        lineage = trace_lineage(sql)
        assert lineage.source_tables == ["orders"]
        assert any(c.output_name == "*" for c in lineage.output_columns)

    def test_empty_sql(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        lineage = trace_lineage("")
        assert lineage.source_tables == []
        assert lineage.output_columns == []

    def test_with_store_resolution(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        from seatunnel_agent.text2sql.schema import ColumnSchema, TableSchema, SchemaStore
        tables = [
            TableSchema(database="db", name="orders", columns=[
                ColumnSchema(name="id", dtype="bigint"),
                ColumnSchema(name="amount", dtype="decimal"),
                ColumnSchema(name="city", dtype="string"),
            ], partition_columns=[]),
        ]
        store = SchemaStore(tables)
        sql = "SELECT city, SUM(amount) AS total FROM orders GROUP BY city"
        lineage = trace_lineage(sql, store)
        city_col = next(c for c in lineage.output_columns if c.output_name == "city")
        assert city_col.source_column == "city"

    def test_lineage_card_basic(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        from seatunnel_agent.text2sql_ui import build_lineage_card
        sql = (
            "SELECT o.id, c.name "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id"
        )
        lineage = trace_lineage(sql)
        html = build_lineage_card(lineage)
        assert "Data Lineage" in html
        assert "orders" in html
        assert "customers" in html
        assert "<details" in html

    def test_lineage_card_zh(self):
        from seatunnel_agent.text2sql.lineage import trace_lineage
        from seatunnel_agent.text2sql_ui import build_lineage_card
        sql = "SELECT id, name FROM users WHERE age > 18"
        lineage = trace_lineage(sql)
        html = build_lineage_card(lineage, lang="zh")
        assert "数据血缘" in html
        assert "来源表" in html
        assert "过滤条件" in html


class TestConfigFromEnv:
    """Tests for config_from_env edge cases."""

    def test_missing_host_returns_none(self):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        with patch.dict("os.environ", {}, clear=True):
            assert config_from_env("mysql") is None

    def test_invalid_port_falls_back(self):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        env = {"MYSQL_HOST": "localhost", "MYSQL_PORT": "not_a_number"}
        with patch.dict("os.environ", env, clear=True):
            cfg = config_from_env("mysql")
            assert cfg is not None
            assert cfg.port == 3306

    def test_invalid_timeout_falls_back(self):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        env = {"MYSQL_HOST": "localhost", "MYSQL_TIMEOUT": "bad"}
        with patch.dict("os.environ", env, clear=True):
            cfg = config_from_env("mysql")
            assert cfg is not None
            assert cfg.timeout_s == 300

    def test_unknown_ds_type(self):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        assert config_from_env("nosuchdb") is None

    def test_sparksql_falls_back_to_hive_env(self):
        from seatunnel_agent.text2sql.executor.base import config_from_env
        env = {"HIVE_HOST": "hivehost", "HIVE_PORT": "10000"}
        with patch.dict("os.environ", env, clear=True):
            cfg = config_from_env("sparksql")
            assert cfg is not None
            assert cfg.host == "hivehost"


class TestFavoritesEdgeCases:
    """Tests for favorites store edge cases."""

    def test_max_favorites_cap(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore, _MAX_FAVORITES
        store = FavoritesStore(tmp_path / "favs.json")
        for i in range(_MAX_FAVORITES + 10):
            store.save(f"q{i}", f"SELECT {i}")
        assert len(store.list()) == _MAX_FAVORITES

    def test_delete_nonexistent(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(tmp_path / "favs.json")
        assert store.delete("nonexistent") is False

    def test_corrupted_file(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        p = tmp_path / "favs.json"
        p.write_text("not json", encoding="utf-8")
        store = FavoritesStore(p)
        assert store.list() == []


class TestChatHistory:
    """Tests for chat history persistence."""

    def test_save_and_load(self, tmp_path):
        from seatunnel_agent.text2sql.chat_history import (
            Text2SQLSession, save_t2s_session, load_t2s_session,
            new_session_id, now_iso, HISTORY_DIR,
        )
        with patch.object(
            __import__("seatunnel_agent.text2sql.chat_history", fromlist=["HISTORY_DIR"]),
            "HISTORY_DIR", tmp_path,
        ):
            sid = new_session_id()
            session = Text2SQLSession(
                session_id=sid, title="Test", created_at=now_iso(), updated_at=now_iso(),
                chat_messages=[{"role": "user", "content": "hello"}],
            )
            save_t2s_session(session)
            loaded = load_t2s_session(sid)
            assert loaded is not None
            assert loaded.title == "Test"
            assert len(loaded.chat_messages) == 1

    def test_load_nonexistent(self, tmp_path):
        from seatunnel_agent.text2sql.chat_history import load_t2s_session
        with patch.object(
            __import__("seatunnel_agent.text2sql.chat_history", fromlist=["HISTORY_DIR"]),
            "HISTORY_DIR", tmp_path,
        ):
            assert load_t2s_session("nonexistent123") is None

    def test_invalid_session_id(self):
        from seatunnel_agent.text2sql.chat_history import load_t2s_session
        assert load_t2s_session("../../../etc/passwd") is None

    def test_chat_message_cap(self, tmp_path):
        from seatunnel_agent.text2sql.chat_history import (
            Text2SQLSession, save_t2s_session, load_t2s_session,
            new_session_id, now_iso, _MAX_CHAT_MESSAGES,
        )
        with patch.object(
            __import__("seatunnel_agent.text2sql.chat_history", fromlist=["HISTORY_DIR"]),
            "HISTORY_DIR", tmp_path,
        ):
            sid = new_session_id()
            msgs = [{"role": "user", "content": f"msg{i}"} for i in range(_MAX_CHAT_MESSAGES + 50)]
            session = Text2SQLSession(
                session_id=sid, title="Big", created_at=now_iso(), updated_at=now_iso(),
                chat_messages=msgs,
            )
            save_t2s_session(session)
            loaded = load_t2s_session(sid)
            assert loaded is not None
            assert len(loaded.chat_messages) == _MAX_CHAT_MESSAGES

    def test_extract_title(self):
        from seatunnel_agent.text2sql.chat_history import extract_title
        msgs = [{"role": "user", "content": "Show me sales data"}]
        assert extract_title(msgs) == "Show me sales data"
        assert extract_title([]) == "Untitled"


class TestTemplates:
    """Tests for SQL template library."""

    def test_get_template_exists(self):
        from seatunnel_agent.text2sql.templates import get_template
        t = get_template("topn")
        assert t is not None
        assert t["id"] == "topn"
        assert "LIMIT" in t["pattern"]

    def test_get_template_missing(self):
        from seatunnel_agent.text2sql.templates import get_template
        assert get_template("nonexistent") is None

    def test_template_choices_en(self):
        from seatunnel_agent.text2sql.templates import template_choices
        choices = template_choices("en")
        assert len(choices) > 0
        assert all("[" in c for c in choices)

    def test_template_choices_zh(self):
        from seatunnel_agent.text2sql.templates import template_choices
        choices = template_choices("zh")
        assert len(choices) > 0

    def test_template_description(self):
        from seatunnel_agent.text2sql.templates import template_description
        desc = template_description("topn", "en")
        assert "Top N" in desc or "top" in desc.lower()
        assert "```sql" in desc

    def test_template_description_missing(self):
        from seatunnel_agent.text2sql.templates import template_description
        assert template_description("nope") == ""


class TestMdTableXss:
    """Tests for XSS escaping in markdown table output."""

    def test_html_in_cell_escaped(self):
        from seatunnel_agent.text2sql_ui import _md_table
        cols = ["name"]
        rows = [["<script>alert(1)</script>"]]
        result = _md_table(cols, rows)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_html_in_header_escaped(self):
        from seatunnel_agent.text2sql_ui import _md_table
        cols = ["<b>name</b>"]
        rows = [["value"]]
        result = _md_table(cols, rows)
        assert "<b>" not in result
        assert "&lt;b&gt;" in result


class TestChartEdgeCases:
    """Tests for chart building edge cases."""

    def test_empty_rows(self):
        from seatunnel_agent.text2sql.chart import build_chart
        assert build_chart(["a", "b"], [], "bar") is None

    def test_empty_columns(self):
        from seatunnel_agent.text2sql.chart import build_chart
        assert build_chart([], [(1, 2)], "bar") is None

    def test_no_numeric_columns(self):
        from seatunnel_agent.text2sql.chart import build_chart
        result = build_chart(["a", "b"], [("x", "y"), ("m", "n")], "bar")
        assert result is None

    def test_scatter_single_numeric(self):
        import matplotlib.pyplot as plt
        from seatunnel_agent.text2sql.chart import build_chart
        fig = build_chart(["cat", "val"], [("a", 1), ("b", 2)], "scatter")
        assert fig is not None
        plt.close(fig)

    def test_unknown_chart_type(self):
        from seatunnel_agent.text2sql.chart import build_chart
        assert build_chart(["a", "b"], [("x", 1)], "unknown_type") is None

    def test_detect_no_numeric(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        assert detect_chart_type(["a", "b"], [("x", "y"), ("m", "n")]) is None

    def test_detect_single_row(self):
        from seatunnel_agent.text2sql.chart import detect_chart_type
        assert detect_chart_type(["a", "b"], [(1, 2)]) is None


class TestExporterEdgeCases:
    """Tests for exporter edge cases."""

    def test_csv_ragged_rows(self, tmp_path):
        from seatunnel_agent.text2sql.exporter import export_csv
        path = export_csv(["a", "b", "c"], [("x",), ("y", "z")], str(tmp_path / "test.csv"))
        content = Path(path).read_text(encoding="utf-8-sig")
        lines = content.strip().split("\n")
        assert len(lines) == 3
        assert lines[1].count(",") == 2

    def test_csv_empty_rows(self, tmp_path):
        from seatunnel_agent.text2sql.exporter import export_csv
        path = export_csv(["a", "b"], [], str(tmp_path / "empty.csv"))
        content = Path(path).read_text(encoding="utf-8-sig")
        lines = content.strip().split("\n")
        assert len(lines) == 1

    def test_excel_export(self, tmp_path):
        pytest.importorskip("openpyxl")
        from seatunnel_agent.text2sql.exporter import export_excel
        path = export_excel(["x", "y"], [(1, 2), (3, 4)], str(tmp_path / "test.xlsx"))
        assert Path(path).exists()
        assert path.endswith(".xlsx")

    def test_excel_ragged_rows(self, tmp_path):
        pytest.importorskip("openpyxl")
        from seatunnel_agent.text2sql.exporter import export_excel
        path = export_excel(["a", "b", "c"], [("x",)], str(tmp_path / "ragged.xlsx"))
        assert Path(path).exists()


class TestQlogEdgeCases:
    """Tests for query logger edge cases."""

    def test_concurrent_writes(self, tmp_path):
        import threading
        logger = QueryLogger(log_dir=str(tmp_path))
        errors = []

        def writer(n):
            try:
                for i in range(20):
                    logger.log(f"q{n}_{i}", f"SELECT {n}_{i}", "success")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(logger.recent(200)) == 100

    def test_clear(self, tmp_path):
        logger = QueryLogger(log_dir=str(tmp_path))
        logger.log("q1", "SELECT 1", "success")
        assert len(logger.recent()) > 0
        logger.clear()
        assert len(logger.recent()) == 0


class TestValidatorExtras:
    """Tests for validator functions not covered elsewhere."""

    def test_strip_literals_and_comments(self):
        from seatunnel_agent.text2sql.validator import _strip_literals_and_comments
        sql = "SELECT * FROM t WHERE name = 'hello' -- comment"
        cleaned = _strip_literals_and_comments(sql)
        assert "hello" not in cleaned
        assert "comment" not in cleaned
        assert "SELECT" in cleaned

    def test_extract_cte_names(self):
        from seatunnel_agent.text2sql.validator import _extract_cte_names
        sql = "WITH cte1 AS (SELECT 1), cte2 AS (SELECT 2) SELECT * FROM cte1"
        names = _extract_cte_names(sql)
        assert "cte1" in names
        assert "cte2" in names

    def test_classify_error_column_not_found(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("column not found 'foo' in any table")
        assert etype == "column_not_found"

    def test_classify_error_syntax(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("syntax error at or near 'SELEC'")
        assert etype == "syntax_error"

    def test_classify_error_type_mismatch(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("cannot cast string to int: type mismatch")
        assert etype == "type_mismatch"

    def test_classify_error_unknown(self):
        from seatunnel_agent.text2sql.tools import classify_error
        etype, hint = classify_error("something completely unrecognized happened")
        assert etype == "execution_error"


# ------------------------------------------------------------------
# Direction 13: Data Profiling
# ------------------------------------------------------------------

class TestProfiler:
    def test_build_profile_sql(self):
        from seatunnel_agent.text2sql.profiler import build_profile_sql
        cols = [{"name": "id", "type": "int"}, {"name": "name", "type": "string"}]
        sql = build_profile_sql("db.users", cols)
        assert "COUNT(*)" in sql
        assert "id__non_null" in sql
        assert "name__distinct" in sql
        assert "FROM db.users" in sql

    def test_build_profile_sql_max_columns(self):
        from seatunnel_agent.text2sql.profiler import build_profile_sql
        cols = [{"name": f"col{i}", "type": "string"} for i in range(30)]
        sql = build_profile_sql("t", cols)
        assert "col19__non_null" in sql
        assert "col20" not in sql

    def test_parse_profile_result(self):
        from seatunnel_agent.text2sql.profiler import parse_profile_result
        cols = [{"name": "id", "type": "int"}, {"name": "name", "type": "string"}]
        row = (100, 100, 100, 1, 100, 98, 50, "Alice", "Zoe")
        profile = parse_profile_result("db.users", cols, row)
        assert profile.row_count == 100
        assert profile.table_name == "db.users"
        assert len(profile.columns) == 2
        assert profile.columns[0].name == "id"
        assert profile.columns[0].null_count == 0
        assert profile.columns[0].distinct_count == 100
        assert profile.columns[1].null_count == 2

    def test_parse_empty_table(self):
        from seatunnel_agent.text2sql.profiler import parse_profile_result
        cols = [{"name": "x", "type": "int"}]
        row = (0, 0, 0, None, None)
        profile = parse_profile_result("t", cols, row)
        assert profile.row_count == 0
        assert profile.columns[0].null_count == 0

    def test_profile_card(self):
        from seatunnel_agent.text2sql.profiler import TableProfile, ColumnProfile
        from seatunnel_agent.text2sql_ui import build_profile_card
        profile = TableProfile(
            table_name="db.t",
            row_count=50,
            columns=[ColumnProfile("id", "int", 50, 0, 50, 1, 50)],
        )
        html = build_profile_card(profile, "en")
        assert "Table Profile" in html
        assert "db.t" in html
        assert "50" in html


# ------------------------------------------------------------------
# Direction 14: SQL Formatter
# ------------------------------------------------------------------

class TestSqlFormatter:
    def test_simple_select(self):
        from seatunnel_agent.text2sql.formatter import format_sql
        result = format_sql("select a, b from t where a > 1")
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result

    def test_preserves_strings(self):
        from seatunnel_agent.text2sql.formatter import format_sql
        result = format_sql("select * from t where name = 'hello world'")
        assert "'hello world'" in result

    def test_empty_sql(self):
        from seatunnel_agent.text2sql.formatter import format_sql
        assert format_sql("") == ""
        assert format_sql("   ") == "   "

    def test_join_formatting(self):
        from seatunnel_agent.text2sql.formatter import format_sql
        sql = "select a.id from t1 a join t2 b on a.id = b.id where a.x > 1"
        result = format_sql(sql)
        assert "JOIN" in result
        assert "ON" in result

    def test_keywords_uppercased(self):
        from seatunnel_agent.text2sql.formatter import format_sql
        result = format_sql("select distinct a from t order by a limit 10")
        assert "SELECT" in result
        assert "DISTINCT" in result
        assert "ORDER BY" in result
        assert "LIMIT" in result


# ------------------------------------------------------------------
# Direction 15: Query Result Diff
# ------------------------------------------------------------------

class TestResultDiff:
    def test_no_diff(self):
        from seatunnel_agent.text2sql.differ import diff_results
        cols = ["a", "b"]
        rows = [(1, 2), (3, 4)]
        diff = diff_results(cols, rows, cols, rows)
        assert not diff.has_changes

    def test_added_rows(self):
        from seatunnel_agent.text2sql.differ import diff_results
        old_rows = [(1, 2)]
        new_rows = [(1, 2), (3, 4)]
        diff = diff_results(["a", "b"], old_rows, ["a", "b"], new_rows)
        assert diff.has_changes
        assert len(diff.added_rows) == 1
        assert (3, 4) in diff.added_rows

    def test_removed_rows(self):
        from seatunnel_agent.text2sql.differ import diff_results
        old_rows = [(1, 2), (3, 4)]
        new_rows = [(1, 2)]
        diff = diff_results(["a", "b"], old_rows, ["a", "b"], new_rows)
        assert len(diff.removed_rows) == 1

    def test_column_changes(self):
        from seatunnel_agent.text2sql.differ import diff_results
        diff = diff_results(["a", "b"], [], ["a", "c"], [])
        assert diff.columns_added == ["c"]
        assert diff.columns_removed == ["b"]

    def test_diff_card_html(self):
        from seatunnel_agent.text2sql_ui import build_diff_card
        diff_data = {"added_count": 3, "removed_count": 1, "cols_added": ["c"],
                     "cols_removed": [], "old_count": 10, "new_count": 12}
        html = build_diff_card(diff_data, "en")
        assert "Result Diff" in html
        assert "+3" in html


# ------------------------------------------------------------------
# Direction 16: Smart JOIN Recommendation
# ------------------------------------------------------------------

class TestJoinAdvisor:
    def _build_store(self):
        ddl = """
        CREATE TABLE db.users(
          id int COMMENT 'pk',
          name string COMMENT 'name',
          dept_id int COMMENT 'department FK'
        ) COMMENT 'users';

        CREATE TABLE db.orders(
          order_id int COMMENT 'pk',
          user_id int COMMENT 'user FK',
          amount decimal(10,2) COMMENT 'amount'
        ) COMMENT 'orders';

        CREATE TABLE db.departments(
          id int COMMENT 'pk',
          dept_name string COMMENT 'dept name'
        ) COMMENT 'departments';
        """
        from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
        return SchemaStore(parse_ddl(ddl))

    def test_exact_name_match(self):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        store = self._build_store()
        suggestions = suggest_joins("db.orders", store)
        exact = [s for s in suggestions if s.match_type == "exact_name"]
        cols = {(s.column_a, s.table_b) for s in exact}
        assert ("user_id", "db.users") not in cols  # user_id only in orders, users has no user_id

    def test_fk_pattern(self):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        store = self._build_store()
        suggestions = suggest_joins("db.users", store)
        fk = [s for s in suggestions if s.match_type == "fk_pattern"]
        pairs = {(s.column_a, s.column_b, s.table_b) for s in fk}
        assert ("id", "user_id", "db.orders") in pairs

    def test_reverse_fk(self):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        store = self._build_store()
        suggestions = suggest_joins("db.orders", store)
        fk = [s for s in suggestions if s.match_type == "fk_pattern"]
        pairs = {(s.column_a, s.column_b, s.table_b) for s in fk}
        assert ("user_id", "id", "db.users") in pairs

    def test_no_suggestions_single_table(self):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
        store = SchemaStore(parse_ddl("CREATE TABLE t(x int) COMMENT 't';"))
        assert suggest_joins("t", store) == []

    def test_confidence_ordering(self):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        store = self._build_store()
        suggestions = suggest_joins("db.users", store)
        if len(suggestions) >= 2:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence >= suggestions[i + 1].confidence


# ------------------------------------------------------------------
# Direction 17: Data Quality Check
# ------------------------------------------------------------------

class TestQualityCheck:
    def test_no_warnings_clean_data(self):
        from seatunnel_agent.text2sql.quality import check_quality
        report = check_quality(["a", "b"], [(1, 2), (3, 4), (5, 6)])
        assert not report.has_warnings

    def test_high_null_warning(self):
        from seatunnel_agent.text2sql.quality import check_quality
        rows = [(None,), (None,), (None,), (1,)]
        report = check_quality(["x"], rows)
        assert report.has_warnings
        types = [w.warning_type for w in report.warnings]
        assert "high_null" in types

    def test_constant_column(self):
        from seatunnel_agent.text2sql.quality import check_quality
        rows = [(42, "a"), (42, "b"), (42, "c")]
        report = check_quality(["val", "name"], rows)
        types = {w.warning_type for w in report.warnings}
        assert "constant" in types

    def test_outlier_detection(self):
        from seatunnel_agent.text2sql.quality import check_quality
        rows = [(i,) for i in range(100)]
        rows.append((99999,))
        report = check_quality(["val"], rows)
        types = {w.warning_type for w in report.warnings}
        assert "outlier" in types

    def test_duplicate_rows(self):
        from seatunnel_agent.text2sql.quality import check_quality
        rows = [(1, 2), (1, 2), (3, 4)]
        report = check_quality(["a", "b"], rows)
        assert report.duplicate_count == 1
        types = {w.warning_type for w in report.warnings}
        assert "duplicate_rows" in types

    def test_quality_card_html(self):
        from seatunnel_agent.text2sql_ui import build_quality_card
        warnings = [{"column": "x", "warning_type": "high_null", "detail": "8/10 (80%)"}]
        html = build_quality_card(warnings, "en")
        assert "Data Quality" in html
        assert "high_null" in html.lower() or "High NULL" in html

    def test_empty_result(self):
        from seatunnel_agent.text2sql.quality import check_quality
        report = check_quality(["a"], [])
        assert not report.has_warnings


# ------------------------------------------------------------------
# Direction 18: Parameterized Favorites
# ------------------------------------------------------------------

class TestParameterizedFavorites:
    def test_extract_params(self):
        from seatunnel_agent.text2sql.favorites import extract_params
        params = extract_params("SELECT * FROM t WHERE date = '${start_date}' AND city = '${city}'")
        assert params == ["start_date", "city"]

    def test_extract_params_none(self):
        from seatunnel_agent.text2sql.favorites import extract_params
        assert extract_params("SELECT * FROM t") == []

    def test_extract_params_duplicates(self):
        from seatunnel_agent.text2sql.favorites import extract_params
        params = extract_params("${x} = 1 AND ${x} = 2")
        assert params == ["x"]

    def test_apply_params(self):
        from seatunnel_agent.text2sql.favorites import apply_params
        result = apply_params(
            "SELECT * FROM t WHERE d = '${date}' AND c = '${city}'",
            {"date": "2024-01-01", "city": "Beijing"},
        )
        assert "2024-01-01" in result
        assert "Beijing" in result
        assert "${" not in result

    def test_apply_params_missing(self):
        from seatunnel_agent.text2sql.favorites import apply_params
        with pytest.raises(ValueError, match="Missing value"):
            apply_params("SELECT * WHERE x = '${missing}'", {})

    def test_save_with_params(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(tmp_path / "fav.json")
        entry = store.save("q1", "SELECT * WHERE d = '${date}'")
        assert entry["params"] == ["date"]

    def test_save_without_params(self, tmp_path):
        from seatunnel_agent.text2sql.favorites import FavoritesStore
        store = FavoritesStore(tmp_path / "fav.json")
        entry = store.save("q2", "SELECT * FROM t")
        assert entry["params"] == []
