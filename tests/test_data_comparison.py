"""Tests for the Data Comparison agent."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

import pytest

from seatunnel_agent.data_comparison.comparator import (
    AggregateItem,
    AggregateResult,
    AlertRule,
    BatchFullItem,
    ChecksumItem,
    ChecksumResult,
    ColumnMapping,
    CompareReport,
    CustomAggItem,
    CustomAggResult,
    KeyedDiffResult,
    ModifiedRow,
    PartitionCompareItem,
    PartitionResult,
    ProfileItem,
    ProfileResult,
    QualityResult,
    QualityRule,
    RowCountResult,
    SchemaDiffResult,
    SchemaDiffItem,
    SkewBucket,
    SkewItem,
    SkewResult,
    ThresholdConfig,
    _close_enough,
    _sql_literal,
    apply_column_mapping,
    build_aggregate_sql,
    build_checksum_sql,
    build_count_sql,
    build_custom_agg_sql,
    build_incremental_sql,
    build_jdbc_url,
    build_partition_count_sql,
    build_profile_sql,
    build_random_sample_sql,
    build_row_count_result,
    build_sample_sql,
    build_skew_sql,
    build_stratified_sample_sql,
    check_trend_alerts,
    parse_alert_rules,
    TrendAlert,
    build_trend_data,
    check_aggregate_threshold,
    check_quality_rules,
    check_row_count_threshold,
    compare_aggregates,
    compare_checksums,
    compare_custom_aggs,
    compare_partitions,
    compare_profiles,
    compare_schemas,
    compare_skew,
    compute_skew_metrics,
    detect_sensitive_columns,
    diff_by_key,
    find_common_tables,
    generate_diff_sql,
    generate_sync_config,
    get_jdbc_driver,
    is_numeric_type,
    mask_rows,
    mask_value,
    parse_column_mapping,
    parse_custom_agg_expressions,
    parse_quality_rules,
    parse_threshold,
    quote_identifier,
    run_parallel,
)
from seatunnel_agent.data_comparison.i18n import DC_I18N, dc
from seatunnel_agent.data_comparison.presets import ConnectionPresetsStore
from seatunnel_agent.data_comparison.templates_store import ComparisonTemplatesStore
from seatunnel_agent.data_comparison.comparator import _row_limit, _escape_hocon
from seatunnel_agent.text2sql.executor.base import QueryResult
from seatunnel_agent.data_comparison_ui import (
    _error_html,
    _esc_html,
    _export_report_csv,
    _send_webhook,
    _validate_where,
    build_aggregate_card,
    build_batch_count_card,
    build_batch_full_card,
    build_batch_template_card,
    build_checksum_card,
    build_count_card,
    build_custom_agg_card,
    build_diff_sql_card,
    build_keyed_diff_card,
    build_lineage_card,
    build_partition_card,
    build_profile_card,
    build_quality_card,
    build_report_diff_card,
    build_skew_card,
    build_sample_diff_card,
    build_schema_diff_card,
    build_standalone_report,
    build_summary_card,
    build_trend_alert_card,
)
from seatunnel_agent.text2sql.differ import ResultDiff


# ── TestComparator ──


class TestSchemaCompare:
    """Tests for compare_schemas()."""

    def test_identical(self):
        cols = [{"name": "id", "type": "INT"}, {"name": "name", "type": "VARCHAR"}]
        result = compare_schemas(cols, cols)
        assert not result.has_changes
        assert result.cols_only_a == 0
        assert result.cols_only_b == 0

    def test_added_column(self):
        cols_a = [{"name": "id", "type": "INT"}]
        cols_b = [{"name": "id", "type": "INT"}, {"name": "age", "type": "INT"}]
        result = compare_schemas(cols_a, cols_b, "t1", "t2")
        assert result.has_changes
        assert result.cols_only_b == 1
        assert result.cols_only_a == 0
        assert any(i.status == "added" and i.column == "age" for i in result.items)

    def test_removed_column(self):
        cols_a = [{"name": "id", "type": "INT"}, {"name": "old_col", "type": "TEXT"}]
        cols_b = [{"name": "id", "type": "INT"}]
        result = compare_schemas(cols_a, cols_b)
        assert result.cols_only_a == 1
        assert any(i.status == "removed" and i.column == "old_col" for i in result.items)

    def test_type_changed(self):
        cols_a = [{"name": "val", "type": "INT"}]
        cols_b = [{"name": "val", "type": "BIGINT"}]
        result = compare_schemas(cols_a, cols_b)
        assert result.type_changes == 1
        item = result.items[0]
        assert item.status == "type_changed"
        assert item.type_a == "INT"
        assert item.type_b == "BIGINT"

    def test_mixed_changes(self):
        cols_a = [
            {"name": "id", "type": "INT"},
            {"name": "old_col", "type": "TEXT"},
            {"name": "val", "type": "INT"},
        ]
        cols_b = [
            {"name": "id", "type": "INT"},
            {"name": "new_col", "type": "VARCHAR"},
            {"name": "val", "type": "BIGINT"},
        ]
        result = compare_schemas(cols_a, cols_b)
        assert result.cols_only_a == 1
        assert result.cols_only_b == 1
        assert result.type_changes == 1

    def test_case_insensitive(self):
        cols_a = [{"name": "ID", "type": "INT"}]
        cols_b = [{"name": "id", "type": "INT"}]
        result = compare_schemas(cols_a, cols_b)
        assert not result.has_changes

    def test_empty_columns(self):
        result = compare_schemas([], [])
        assert not result.has_changes
        assert result.items == []

    def test_both_empty_vs_nonempty(self):
        result = compare_schemas([], [{"name": "id", "type": "INT"}])
        assert result.has_changes
        assert result.cols_only_b == 1


class TestSqlBuilders:
    """Tests for SQL generation functions."""

    def test_build_count_sql(self):
        sql = build_count_sql("my_table")
        assert "COUNT(*)" in sql
        assert "my_table" in sql

    def test_build_sample_sql(self):
        sql = build_sample_sql("my_table", 50)
        assert "SELECT *" in sql
        assert "LIMIT 50" in sql
        assert "my_table" in sql

    def test_build_sample_sql_default_limit(self):
        sql = build_sample_sql("t")
        assert "LIMIT 100" in sql

    def test_build_aggregate_sql(self):
        sql = build_aggregate_sql("orders", ["amount", "qty"])
        assert "SUM(amount)" in sql
        assert "AVG(amount)" in sql
        assert "MIN(qty)" in sql
        assert "MAX(qty)" in sql
        assert "amount__null" in sql
        assert "orders" in sql

    def test_build_aggregate_sql_empty_columns(self):
        sql = build_aggregate_sql("t", [])
        assert "COUNT(*)" in sql

    def test_build_aggregate_sql_formatting(self):
        sql = build_aggregate_sql("orders", ["amount"])
        assert "\n" in sql
        assert "FROM orders" in sql

    def test_build_aggregate_sql_caps_at_20(self):
        cols = [f"c{i}" for i in range(25)]
        sql = build_aggregate_sql("t", cols)
        assert "c19" in sql
        assert "c20" not in sql

    def test_build_count_sql_quotes_special_name(self):
        sql = build_count_sql("my table")
        assert '"my table"' in sql

    def test_build_sample_sql_int_limit(self):
        sql = build_sample_sql("t", 50)
        assert "LIMIT 50" in sql


class TestAggregateCompare:
    """Tests for compare_aggregates()."""

    def test_match(self):
        row = (100, 500, 5.0, 1, 10, 0, 200, 2.0, 1, 20, 5)
        result = compare_aggregates("t1", row, "t2", row, ["a", "b"])
        assert result.mismatches == 0
        assert all(item.match for item in result.items)

    def test_mismatch(self):
        row_a = (100, 500, 5.0, 1, 10, 0)
        row_b = (100, 999, 9.9, 1, 10, 0)
        result = compare_aggregates("t1", row_a, "t2", row_b, ["x"])
        assert result.mismatches > 0
        assert any(not item.match for item in result.items)

    def test_empty_columns(self):
        result = compare_aggregates("t1", (), "t2", (), [])
        assert result.mismatches == 0
        assert len(result.items) == 0


class TestIsNumericType:
    """Tests for is_numeric_type()."""

    def test_basic_numeric(self):
        assert is_numeric_type("INT")
        assert is_numeric_type("bigint")
        assert is_numeric_type("DECIMAL(10,2)")
        assert is_numeric_type("float")

    def test_non_numeric(self):
        assert not is_numeric_type("VARCHAR")
        assert not is_numeric_type("TEXT")
        assert not is_numeric_type("DATE")
        assert not is_numeric_type("BOOLEAN")

    def test_extended_numeric_types(self):
        assert is_numeric_type("serial")
        assert is_numeric_type("BIGSERIAL")
        assert is_numeric_type("money")
        assert is_numeric_type("SMALLSERIAL")


class TestFindCommonTables:
    """Tests for find_common_tables()."""

    def test_exact_match(self):
        result = find_common_tables(["users", "orders"], ["orders", "users"])
        assert len(result) == 2

    def test_case_insensitive(self):
        result = find_common_tables(["Users"], ["users"])
        assert len(result) == 1
        assert result[0] == ("Users", "users")

    def test_no_common(self):
        result = find_common_tables(["a", "b"], ["c", "d"])
        assert len(result) == 0

    def test_partial_overlap(self):
        result = find_common_tables(["a", "b", "c"], ["b", "d"])
        assert len(result) == 1
        assert result[0][0] == "b"


class TestBuildRowCountResult:
    """Tests for build_row_count_result()."""

    def test_match(self):
        r = build_row_count_result("t1", 100, "t2", 100)
        assert r.delta == 0
        assert r.delta_pct == 0.0

    def test_delta(self):
        r = build_row_count_result("t1", 150, "t2", 100)
        assert r.delta == 50
        assert r.delta_pct > 0

    def test_both_zero(self):
        r = build_row_count_result("t1", 0, "t2", 0)
        assert r.delta == 0
        assert r.delta_pct == 0.0


class TestCompareReport:
    """Tests for CompareReport dataclass."""

    def test_defaults(self):
        report = CompareReport()
        assert report.schema is None
        assert report.row_count is None
        assert report.sample is None
        assert report.aggregate is None
        assert report.batch_counts is None
        assert report.elapsed_ms == 0

    def test_populated(self):
        schema = SchemaDiffResult("t1", "t2")
        count = RowCountResult("t1", 100, "t2", 100, 0, 0.0)
        report = CompareReport(schema=schema, row_count=count, elapsed_ms=42)
        assert report.schema is not None
        assert report.row_count is not None
        assert report.elapsed_ms == 42


# ── TestCards ──


class TestCards:
    """Tests for HTML card builders."""

    def test_schema_diff_card_identical(self):
        result = SchemaDiffResult("t1", "t2")
        html = build_schema_diff_card(result, "en")
        assert "identical" in html.lower() or "dc_identical" in html

    def test_schema_diff_card_changes(self):
        result = SchemaDiffResult(
            "t1", "t2",
            items=[SchemaDiffItem("col1", "added", type_b="INT")],
            cols_only_b=1,
        )
        html = build_schema_diff_card(result, "en")
        assert "col1" in html
        assert "Added" in html

    def test_count_card_match(self):
        result = RowCountResult("t1", 100, "t2", 100, 0, 0.0)
        html = build_count_card(result, "en")
        assert "Match" in html
        assert "100" in html

    def test_count_card_delta(self):
        result = RowCountResult("t1", 100, "t2", 50, 50, 100.0)
        html = build_count_card(result, "en")
        assert "50" in html
        assert "Delta" in html

    def test_sample_diff_card_no_diff(self):
        diff = ResultDiff()
        html = build_sample_diff_card(diff, "en")
        assert "No differences" in html or "dc_no_diff" in html

    def test_sample_diff_card_with_changes(self):
        diff = ResultDiff(
            added_rows=[(1, "a"), (2, "b")],
            removed_rows=[(3, "c")],
            old_count=5,
            new_count=6,
        )
        html = build_sample_diff_card(diff, "en")
        assert "+2" in html
        assert "-1" in html

    def test_sample_diff_card_shows_rows(self):
        diff = ResultDiff(
            added_rows=[(1, "alice"), (2, "bob")],
            removed_rows=[(3, "charlie")],
            old_count=5,
            new_count=6,
        )
        html = build_sample_diff_card(diff, "en", columns=["id", "name"])
        assert "alice" in html
        assert "bob" in html
        assert "charlie" in html
        assert "id" in html
        assert "name" in html

    def test_aggregate_card_no_items(self):
        result = AggregateResult("t1", "t2")
        html = build_aggregate_card(result, "en")
        assert "No shared numeric" in html or "dc_no_numeric" in html

    def test_aggregate_card_with_items(self):
        result = AggregateResult(
            "t1", "t2",
            items=[
                AggregateItem("price", "sum", 100.0, 100.0, True),
                AggregateItem("price", "avg", 10.0, 20.0, False),
            ],
            mismatches=1,
        )
        html = build_aggregate_card(result, "en")
        assert "price" in html
        assert "Mismatch" in html

    def test_aggregate_card_zero_value_not_null(self):
        result = AggregateResult(
            "t1", "t2",
            items=[AggregateItem("qty", "min", 0, 0, True)],
            mismatches=0,
        )
        html = build_aggregate_card(result, "en")
        assert "NULL" not in html
        assert "0" in html

    def test_batch_count_card_empty(self):
        html = build_batch_count_card([], "en")
        assert "No common" in html or "dc_no_common" in html

    def test_batch_count_card_with_results(self):
        results = [
            RowCountResult("users", 100, "users", 100, 0, 0.0),
            RowCountResult("orders", 200, "orders", 150, 50, 33.3),
        ]
        html = build_batch_count_card(results, "en")
        assert "users" in html
        assert "orders" in html
        assert "Match" in html
        assert "+50" in html

    def test_summary_card_no_diffs(self):
        report = CompareReport(
            schema=SchemaDiffResult("t1", "t2"),
            row_count=RowCountResult("t1", 100, "t2", 100, 0, 0.0),
            elapsed_ms=150,
        )
        html = build_summary_card(report, "en")
        assert "Summary" in html
        assert "150" in html
        assert "matched" in html.lower() or "All matched" in html

    def test_summary_card_with_diffs(self):
        report = CompareReport(
            schema=SchemaDiffResult("t1", "t2", items=[SchemaDiffItem("x", "added", type_b="INT")]),
            row_count=RowCountResult("t1", 100, "t2", 50, 50, 100.0),
            elapsed_ms=200,
        )
        html = build_summary_card(report, "en")
        assert "2" in html
        assert "difference" in html.lower()

    def test_summary_card_zero_elapsed(self):
        report = CompareReport(
            schema=SchemaDiffResult("t1", "t2"),
            elapsed_ms=0,
        )
        html = build_summary_card(report, "en")
        assert "elapsed" not in html


# ── TestQuoteIdentifier ──


class TestQuoteIdentifier:
    """Tests for quote_identifier()."""

    def test_simple_name_unchanged(self):
        assert quote_identifier("users") == "users"
        assert quote_identifier("my_table") == "my_table"
        assert quote_identifier("schema1.table2") == "schema1.table2"

    def test_special_chars_quoted(self):
        result = quote_identifier("table name")
        assert result == '"table name"'

    def test_embedded_double_quote_escaped(self):
        result = quote_identifier('my"table')
        assert result == '"my""table"'

    def test_sql_injection_attempt_quoted(self):
        result = quote_identifier("t; DROP TABLE users; --")
        assert result.startswith('"')
        assert result.endswith('"')


# ── TestCloseEnough ──


class TestCloseEnough:
    """Tests for _close_enough()."""

    def test_both_none(self):
        assert _close_enough(None, None)

    def test_one_none(self):
        assert not _close_enough(None, 1)
        assert not _close_enough(1, None)

    def test_exact_match(self):
        assert _close_enough(100, 100)
        assert _close_enough(0, 0)
        assert _close_enough(0.0, 0.0)

    def test_close_floats(self):
        assert _close_enough(1.0, 1.0 + 1e-10)

    def test_not_close(self):
        assert not _close_enough(1.0, 2.0)

    def test_nan_both(self):
        assert _close_enough(float("nan"), float("nan"))

    def test_nan_one(self):
        assert not _close_enough(float("nan"), 1.0)
        assert not _close_enough(1.0, float("nan"))

    def test_string_fallback(self):
        assert _close_enough("abc", "abc")
        assert not _close_enough("abc", "def")


# ── TestEscHtml ──


class TestEscHtml:
    """Tests for _esc_html()."""

    def test_basic_escaping(self):
        assert _esc_html("<script>") == "&lt;script&gt;"
        assert _esc_html("a & b") == "a &amp; b"

    def test_quote_escaping(self):
        assert _esc_html('"hello"') == "&quot;hello&quot;"

    def test_none_coerced(self):
        assert _esc_html(None) == "None"


# ── TestExportCsv ──


class TestExportCsv:
    """Tests for _export_report_csv()."""

    def test_export_csv_creates_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "seatunnel_agent.data_comparison_ui.default_desktop_dir",
            lambda: tmp_path,
        )
        report = CompareReport(
            schema=SchemaDiffResult("t1", "t2"),
            row_count=RowCountResult("t1", 100, "t2", 50, 50, 100.0),
        )
        path = _export_report_csv(report)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8-sig").read()
        assert "[Schema Diff]" in content
        assert "[Row Count]" in content
        assert "100" in content

    def test_export_csv_empty_report(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "seatunnel_agent.data_comparison_ui.default_desktop_dir",
            lambda: tmp_path,
        )
        report = CompareReport()
        path = _export_report_csv(report)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8-sig").read()
        assert content.strip() == ""


# ── TestI18n ──


class TestI18n:
    """Tests for data comparison i18n."""

    def test_all_en_keys_have_zh(self):
        en_keys = set(DC_I18N["en"].keys())
        zh_keys = set(DC_I18N["zh"].keys())
        missing = en_keys - zh_keys
        assert not missing, f"Missing zh keys: {missing}"

    def test_accessor(self):
        assert dc("en", "dc_title") == "### Data Comparison"
        assert dc("zh", "dc_title") == "### 数据比对"

    def test_fallback_to_en(self):
        assert dc("fr", "dc_title") == "### Data Comparison"

    def test_missing_key_returns_key(self):
        assert dc("en", "nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_new_keys_present(self):
        for key in ("dc_summary", "dc_batch_count", "dc_sample_preview",
                     "dc_elapsed", "dc_common_tables", "dc_showing_n_rows"):
            assert key in DC_I18N["en"], f"Missing en key: {key}"
            assert key in DC_I18N["zh"], f"Missing zh key: {key}"

    def test_round3_keys_present(self):
        round3_keys = [
            "dc_key_columns", "dc_key_diff", "dc_modified_rows",
            "dc_old_val", "dc_new_val",
            "dc_custom_sql", "dc_compare_sql", "dc_sql_placeholder", "dc_sql_readonly_only",
            "dc_profile", "dc_profile_result", "dc_distinct", "dc_null_rate", "dc_min", "dc_max",
            "dc_where_clause", "dc_where_hint", "dc_where_invalid",
            "dc_save_report", "dc_load_report", "dc_saved", "dc_loaded", "dc_no_reports",
            "dc_comparing_table",
            "dc_view_report", "dc_report_title", "dc_no_report", "dc_print",
        ]
        for key in round3_keys:
            assert key in DC_I18N["en"], f"Missing en key: {key}"
            assert key in DC_I18N["zh"], f"Missing zh key: {key}"


# ── TestDiffByKey (A) ──


class TestDiffByKey:
    """Tests for diff_by_key()."""

    def test_identical(self):
        cols = ["id", "name"]
        rows = [(1, "a"), (2, "b")]
        result = diff_by_key(cols, rows, cols, rows, ["id"])
        assert not result.added
        assert not result.removed
        assert not result.modified

    def test_added_rows(self):
        cols = ["id", "val"]
        rows_a = [(1, "x")]
        rows_b = [(1, "x"), (2, "y")]
        result = diff_by_key(cols, rows_a, cols, rows_b, ["id"])
        assert len(result.added) == 1
        assert result.added[0] == (2, "y")
        assert not result.removed

    def test_removed_rows(self):
        cols = ["id", "val"]
        rows_a = [(1, "x"), (2, "y")]
        rows_b = [(1, "x")]
        result = diff_by_key(cols, rows_a, cols, rows_b, ["id"])
        assert len(result.removed) == 1
        assert not result.added

    def test_modified_rows(self):
        cols = ["id", "val"]
        rows_a = [(1, "old")]
        rows_b = [(1, "new")]
        result = diff_by_key(cols, rows_a, cols, rows_b, ["id"])
        assert len(result.modified) == 1
        mr = result.modified[0]
        assert mr.key == (1,)
        assert len(mr.changes) == 1
        assert mr.changes[0] == ("val", "old", "new")

    def test_missing_key_column_raises(self):
        cols = ["id", "val"]
        rows = [(1, "x")]
        with pytest.raises(ValueError):
            diff_by_key(cols, rows, cols, rows, ["nonexistent"])

    def test_empty_inputs(self):
        result = diff_by_key(["id"], [], ["id"], [], ["id"])
        assert not result.added
        assert not result.removed
        assert not result.modified

    def test_max_rows_cap(self):
        cols = ["id"]
        rows_a = []
        rows_b = [(i,) for i in range(500)]
        result = diff_by_key(cols, rows_a, cols, rows_b, ["id"], max_rows=10)
        assert len(result.added) == 10

    def test_composite_key(self):
        cols = ["k1", "k2", "val"]
        rows_a = [(1, "a", "old")]
        rows_b = [(1, "a", "new"), (1, "b", "extra")]
        result = diff_by_key(cols, rows_a, cols, rows_b, ["k1", "k2"])
        assert len(result.added) == 1
        assert len(result.modified) == 1


# ── TestProfileSql (C) ──


class TestProfileSql:
    """Tests for build_profile_sql()."""

    def test_basic(self):
        sql = build_profile_sql("t", ["a", "b"])
        assert "COUNT(*)" in sql
        assert "COUNT(DISTINCT" in sql
        assert "MIN(a)" in sql
        assert "MAX(b)" in sql
        assert "t" in sql

    def test_empty_columns(self):
        sql = build_profile_sql("t", [])
        assert "COUNT(*)" in sql

    def test_with_where(self):
        sql = build_profile_sql("t", ["x"], where="x > 0")
        assert "WHERE x > 0" in sql

    def test_caps_at_20(self):
        cols = [f"c{i}" for i in range(25)]
        sql = build_profile_sql("t", cols)
        assert "c19" in sql
        assert "c20" not in sql


# ── TestCompareProfiles (C) ──


class TestCompareProfiles:
    """Tests for compare_profiles()."""

    def test_match(self):
        row = (100, 50, 5, 1, 99, 50, 5, 1, 99)
        result = compare_profiles("t1", row, 100, "t2", row, 100, ["a", "b"])
        assert len(result.items) == 2
        assert result.total_a == 100

    def test_mismatch(self):
        row_a = (100, 50, 5, 1, 99)
        row_b = (200, 80, 10, 2, 199)
        result = compare_profiles("t1", row_a, 100, "t2", row_b, 200, ["a"])
        assert result.items[0].distinct_a == 50
        assert result.items[0].distinct_b == 80

    def test_empty_columns(self):
        result = compare_profiles("t1", (100,), 100, "t2", (100,), 100, [])
        assert len(result.items) == 0


# ── TestWhereClause (D) ──


class TestWhereClause:
    """Tests for WHERE clause support in SQL builders."""

    def test_count_with_where(self):
        sql = build_count_sql("t", where="status = 'active'")
        assert "WHERE status = 'active'" in sql

    def test_sample_with_where(self):
        sql = build_sample_sql("t", 100, where="id > 10")
        assert "WHERE id > 10" in sql
        assert "LIMIT 100" in sql

    def test_aggregate_with_where(self):
        sql = build_aggregate_sql("t", ["amount"], where="date > '2024-01-01'")
        assert "WHERE date > '2024-01-01'" in sql

    def test_empty_where_no_clause(self):
        sql = build_count_sql("t", where="")
        assert "WHERE" not in sql

    def test_whitespace_only_where(self):
        sql = build_count_sql("t", where="   ")
        assert "WHERE" not in sql


# ── TestValidateWhere (D) ──


class TestValidateWhere:
    """Tests for _validate_where()."""

    def test_valid_clause(self):
        ok, msg = _validate_where("status = 'active'", "en")
        assert ok
        assert msg == ""

    def test_empty_clause(self):
        ok, msg = _validate_where("", "en")
        assert ok

    def test_ddl_rejected(self):
        for kw in ("DROP TABLE x", "DELETE FROM t", "INSERT INTO t", "UPDATE t SET x=1",
                    "ALTER TABLE t", "CREATE TABLE t", "TRUNCATE TABLE t"):
            ok, msg = _validate_where(kw, "en")
            assert not ok, f"Should reject: {kw}"
            assert msg  # non-empty error message

    def test_select_in_subquery_ok(self):
        ok, msg = _validate_where("id IN (SELECT id FROM t2)", "en")
        assert ok


# ── TestRunParallel (F) ──


class TestRunParallel:
    """Tests for run_parallel()."""

    def test_both_succeed(self):
        a, b = run_parallel(lambda: 1, lambda: 2)
        assert a == 1
        assert b == 2

    def test_one_raises(self):
        def fail():
            raise ValueError("boom")
        with pytest.raises(ValueError, match="boom"):
            run_parallel(fail, lambda: 2)


# ── TestReportSerialization (E) ──


class TestReportSerialization:
    """Tests for CompareReport to_dict/from_dict."""

    def test_round_trip_empty(self):
        report = CompareReport()
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.schema is None
        assert restored.elapsed_ms == 0

    def test_round_trip_full(self):
        schema = SchemaDiffResult(
            "t1", "t2",
            items=[SchemaDiffItem("col1", "added", type_b="INT")],
            cols_only_b=1,
        )
        count = RowCountResult("t1", 100, "t2", 50, 50, 100.0)
        agg = AggregateResult(
            "t1", "t2",
            items=[AggregateItem("price", "sum", 100.0, 99.0, False)],
            mismatches=1,
        )
        profile = ProfileResult(
            "t1", "t2", 100, 200,
            items=[ProfileItem("x", 10, 20, 5.0, 10.0, 0, 1, 99, 199)],
        )
        keyed = KeyedDiffResult(
            key_columns=["id"], columns=["id", "val"],
            added=[(3, "new")], removed=[(4, "gone")],
            modified=[ModifiedRow(key=(1,), changes=[("val", "a", "b")])],
        )
        batch = [RowCountResult("u", 10, "u", 10, 0, 0.0)]

        report = CompareReport(
            schema=schema, row_count=count, aggregate=agg,
            profile=profile, keyed_diff=keyed, batch_counts=batch,
            elapsed_ms=999,
        )
        d = report.to_dict()
        restored = CompareReport.from_dict(d)

        assert restored.schema.cols_only_b == 1
        assert restored.schema.items[0].column == "col1"
        assert restored.row_count.delta == 50
        assert restored.aggregate.mismatches == 1
        assert restored.profile.items[0].distinct_a == 10
        assert restored.keyed_diff.modified[0].key == (1,)
        assert restored.keyed_diff.added[0] == (3, "new")
        assert restored.batch_counts[0].delta == 0
        assert restored.elapsed_ms == 999


# ── TestBuildKeyedDiffCard (A) ──


class TestBuildKeyedDiffCard:
    """Tests for build_keyed_diff_card()."""

    def test_no_diff(self):
        result = KeyedDiffResult(["id"], ["id", "val"])
        html = build_keyed_diff_card(result, "en")
        assert "No differences" in html or "dc_no_diff" in html

    def test_with_changes(self):
        result = KeyedDiffResult(
            key_columns=["id"], columns=["id", "val"],
            added=[(2, "new")],
            removed=[(3, "gone")],
            modified=[ModifiedRow(key=(1,), changes=[("val", "old", "new")])],
        )
        html = build_keyed_diff_card(result, "en")
        assert "+1" in html  # added
        assert "-1" in html  # removed
        assert "old" in html
        assert "new" in html


# ── TestBuildProfileCard (C) ──


class TestBuildProfileCard:
    """Tests for build_profile_card()."""

    def test_empty(self):
        result = ProfileResult("t1", "t2")
        html = build_profile_card(result, "en")
        assert "Profile" in html

    def test_with_items(self):
        result = ProfileResult(
            "t1", "t2", 100, 200,
            items=[ProfileItem("col1", 50, 80, 5.0, 10.0, 0, 1, 99, 199)],
        )
        html = build_profile_card(result, "en")
        assert "col1" in html
        assert "50" in html
        assert "80" in html
        assert "5.0" in html


# ── TestStandaloneReport ──


class TestStandaloneReport:
    """Tests for build_standalone_report()."""

    def test_empty_report(self):
        report = CompareReport()
        html = build_standalone_report(report, "en")
        assert "<!DOCTYPE html>" in html
        assert "Data Comparison Report" in html

    def test_with_data(self):
        report = CompareReport(
            schema=SchemaDiffResult("t1", "t2"),
            row_count=RowCountResult("t1", 100, "t2", 100, 0, 0.0),
            elapsed_ms=42,
        )
        html = build_standalone_report(report, "en")
        assert "<!DOCTYPE html>" in html
        assert "window.print" in html
        assert "100" in html

    def test_chinese(self):
        report = CompareReport(elapsed_ms=10)
        html = build_standalone_report(report, "zh")
        assert "数据比对报告" in html
        assert "打印" in html


# ── Round 4 tests ──


class TestParseThreshold:
    """Tests for parse_threshold()."""

    def test_percentage(self):
        t = parse_threshold("5%")
        assert t is not None
        assert t.value == 5.0
        assert t.is_percentage is True

    def test_absolute(self):
        t = parse_threshold("100")
        assert t is not None
        assert t.value == 100.0
        assert t.is_percentage is False

    def test_empty(self):
        assert parse_threshold("") is None
        assert parse_threshold("  ") is None

    def test_invalid(self):
        assert parse_threshold("abc") is None

    def test_zero(self):
        t = parse_threshold("0")
        assert t is not None
        assert t.value == 0.0


class TestCheckThreshold:
    """Tests for check_row_count_threshold and check_aggregate_threshold."""

    def test_row_count_within_pct(self):
        r = RowCountResult("t1", 100, "t2", 103, 3, 3.0)
        th = ThresholdConfig(value=5.0, is_percentage=True)
        assert check_row_count_threshold(r, th) is True

    def test_row_count_exceeds_pct(self):
        r = RowCountResult("t1", 100, "t2", 120, 20, 20.0)
        th = ThresholdConfig(value=5.0, is_percentage=True)
        assert check_row_count_threshold(r, th) is False

    def test_row_count_absolute(self):
        r = RowCountResult("t1", 100, "t2", 150, 50, 50.0)
        th = ThresholdConfig(value=50, is_percentage=False)
        assert check_row_count_threshold(r, th) is True

    def test_row_count_exact_boundary(self):
        r = RowCountResult("t1", 100, "t2", 105, 5, 5.0)
        th = ThresholdConfig(value=5.0, is_percentage=True)
        assert check_row_count_threshold(r, th) is True

    def test_aggregate_no_mismatch(self):
        agg = AggregateResult("t1", "t2", [], mismatches=0)
        th = ThresholdConfig(value=5.0)
        assert check_aggregate_threshold(agg, th) is True

    def test_aggregate_with_mismatch(self):
        items = [AggregateItem("col", "SUM", 100.0, 200.0, False)]
        agg = AggregateResult("t1", "t2", items, mismatches=1)
        th = ThresholdConfig(value=5.0)
        assert check_aggregate_threshold(agg, th) is False


class TestColumnMapping:
    """Tests for parse_column_mapping and apply_column_mapping."""

    def test_parse_valid(self):
        m = parse_column_mapping("col_a:col_b, name:full_name")
        assert m == {"col_a": "col_b", "name": "full_name"}

    def test_parse_empty(self):
        assert parse_column_mapping("") == {}
        assert parse_column_mapping("  ") == {}

    def test_parse_invalid_entries_skipped(self):
        m = parse_column_mapping("good:pair, nocolon, another:one")
        assert m == {"good": "pair", "another": "one"}

    def test_apply_mapping(self):
        cols = ["full_name", "age", "col_b"]
        mapping = {"name": "full_name", "col_a": "col_b"}
        result = apply_column_mapping(cols, mapping)
        assert result == ["name", "age", "col_a"]

    def test_apply_no_match(self):
        cols = ["x", "y", "z"]
        mapping = {"a": "b"}
        assert apply_column_mapping(cols, mapping) == ["x", "y", "z"]

    def test_apply_case_insensitive(self):
        cols = ["FULL_NAME", "Age"]
        mapping = {"name": "full_name"}
        result = apply_column_mapping(cols, mapping)
        assert result == ["name", "Age"]


class TestRandomSampleSql:
    """Tests for build_random_sample_sql."""

    def test_mysql(self):
        sql = build_random_sample_sql("orders", 50, "mysql")
        assert "RAND()" in sql
        assert "LIMIT 50" in sql
        assert "orders" in sql

    def test_postgresql(self):
        sql = build_random_sample_sql("orders", 100, "postgresql")
        assert "RANDOM()" in sql

    def test_sqlserver(self):
        sql = build_random_sample_sql("orders", 10, "sqlserver")
        assert "TOP 10" in sql
        assert "NEWID()" in sql

    def test_clickhouse(self):
        sql = build_random_sample_sql("orders", 20, "clickhouse")
        assert "rand()" in sql

    def test_with_where(self):
        sql = build_random_sample_sql("orders", 50, "mysql", where="status='active'")
        assert "WHERE" in sql
        assert "status='active'" in sql

    def test_unknown_dialect_fallback(self):
        sql = build_random_sample_sql("t", 10, "unknown_db")
        assert "LIMIT 10" in sql


class TestBatchFullItem:
    """Tests for BatchFullItem dataclass."""

    def test_no_diffs(self):
        item = BatchFullItem(
            table_a="t1", table_b="t1",
            schema=SchemaDiffResult("t1", "t1"),
            row_count=RowCountResult("t1", 100, "t1", 100, 0, 0.0),
            has_diffs=False,
        )
        assert item.has_diffs is False

    def test_has_schema_diff(self):
        schema = SchemaDiffResult("t1", "t2")
        schema.added = [SchemaDiffItem("col1", None, "INT")]
        item = BatchFullItem("t1", "t2", schema=schema, has_diffs=True)
        assert item.has_diffs is True

    def test_has_count_diff(self):
        rc = RowCountResult("t1", 100, "t2", 200, 100, 100.0)
        item = BatchFullItem("t1", "t2", row_count=rc, has_diffs=True)
        assert item.row_count.delta == 100

    def test_defaults(self):
        item = BatchFullItem("a", "b")
        assert item.schema is None
        assert item.row_count is None
        assert item.aggregate is None
        assert item.has_diffs is False


class TestBuildSyncConfig:
    """Tests for generate_sync_config."""

    def test_mysql_to_mysql(self):
        cfg = generate_sync_config(
            "mysql", "h1", 3306, "db1", "u1", "p1", "src_table",
            "mysql", "h2", 3306, "db2", "u2", "p2", "sink_table",
        )
        assert 'job.mode = "BATCH"' in cfg
        assert "jdbc:mysql://h1:3306/db1" in cfg
        assert "jdbc:mysql://h2:3306/db2" in cfg
        assert "src_table" in cfg
        assert "sink_table" in cfg
        assert "generate_sink_sql = true" in cfg

    def test_pg_to_pg(self):
        cfg = generate_sync_config(
            "postgresql", "h1", 5432, "db1", "u1", "p1", "t1",
            "postgresql", "h2", 5432, "db2", "u2", "p2", "t2",
        )
        assert "jdbc:postgresql://h1:5432/db1" in cfg
        assert "org.postgresql.Driver" in cfg

    def test_with_mapping(self):
        mapping = {"name": "full_name"}
        cfg = generate_sync_config(
            "mysql", "h", 3306, "d", "u", "p", "t1",
            "mysql", "h", 3306, "d", "u", "p", "t2",
            column_mapping=mapping,
        )
        assert "Sql" in cfg
        assert "full_name" in cfg

    def test_no_credentials(self):
        cfg = generate_sync_config(
            "mysql", "h", 3306, "d", None, None, "t1",
            "mysql", "h", 3306, "d", None, None, "t2",
        )
        assert "user" not in cfg.lower() or 'user = "' not in cfg


class TestJdbcHelpers:
    """Tests for build_jdbc_url and get_jdbc_driver."""

    def test_mysql_url(self):
        assert build_jdbc_url("mysql", "host", 3306, "db") == "jdbc:mysql://host:3306/db"

    def test_pg_url(self):
        assert build_jdbc_url("postgresql", "h", 5432, "d") == "jdbc:postgresql://h:5432/d"

    def test_sqlserver_url(self):
        url = build_jdbc_url("sqlserver", "h", 1433, "d")
        assert "databaseName=d" in url

    def test_mysql_driver(self):
        assert get_jdbc_driver("mysql") == "com.mysql.cj.jdbc.Driver"

    def test_unknown_driver(self):
        assert get_jdbc_driver("unknown") == ""


class TestConnectionPresetsStore:
    """Tests for ConnectionPresetsStore."""

    def test_save_and_list(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            store.save("test_conn", "mysql", "localhost", 3306, "testdb", "root", "pass")
            items = store.list()
            assert len(items) == 1
            assert items[0]["name"] == "test_conn"
            assert items[0]["ds_type"] == "mysql"
        finally:
            os.unlink(path)

    def test_get_by_name(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            store.save("c1", "mysql", "h", 3306, "d")
            assert store.get_by_name("c1") is not None
            assert store.get_by_name("nonexistent") is None
        finally:
            os.unlink(path)

    def test_delete(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            entry = store.save("c1", "mysql", "h", 3306, "d")
            assert store.delete(entry["id"]) is True
            assert store.list() == []
        finally:
            os.unlink(path)

    def test_duplicate_name_replaces(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            store.save("c1", "mysql", "h1", 3306, "d1")
            store.save("c1", "postgresql", "h2", 5432, "d2")
            items = store.list()
            assert len(items) == 1
            assert items[0]["ds_type"] == "postgresql"
        finally:
            os.unlink(path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            assert store.list() == []
        finally:
            os.unlink(path)


class TestBuildBatchFullCard:
    """Tests for build_batch_full_card."""

    def test_all_pass(self):
        items = [
            BatchFullItem("t1", "t1",
                          schema=SchemaDiffResult("t1", "t1"),
                          row_count=RowCountResult("t1", 10, "t1", 10, 0, 0.0),
                          has_diffs=False),
        ]
        html = build_batch_full_card(items, "en")
        assert "1 passed" in html
        assert "0 failed" in html

    def test_some_fail(self):
        items = [
            BatchFullItem("t1", "t1", has_diffs=False),
            BatchFullItem("t2", "t2", has_diffs=True),
        ]
        html = build_batch_full_card(items, "en")
        assert "1 passed" in html
        assert "1 failed" in html

    def test_with_threshold(self):
        items = [
            BatchFullItem("t1", "t1",
                          row_count=RowCountResult("t1", 100, "t1", 103, 3, 3.0),
                          has_diffs=False),
        ]
        th = ThresholdConfig(value=5.0, is_percentage=True)
        html = build_batch_full_card(items, "en", threshold=th)
        assert "PASS" in html


class TestThresholdInCountCard:
    """Tests for threshold badges in build_count_card."""

    def test_pass_badge(self):
        r = RowCountResult("t1", 100, "t2", 102, 2, 2.0)
        th = ThresholdConfig(value=5.0, is_percentage=True)
        html = build_count_card(r, "en", threshold=th)
        assert "PASS" in html

    def test_fail_badge(self):
        r = RowCountResult("t1", 100, "t2", 150, 50, 50.0)
        th = ThresholdConfig(value=5.0, is_percentage=True)
        html = build_count_card(r, "en", threshold=th)
        assert "FAIL" in html

    def test_no_threshold(self):
        r = RowCountResult("t1", 100, "t2", 100, 0, 0.0)
        html = build_count_card(r, "en")
        assert "PASS" not in html
        assert "FAIL" not in html


class TestTrendData:
    """Tests for build_trend_data."""

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = build_trend_data(Path(d))
            assert result == []

    def test_no_dir(self):
        result = build_trend_data(Path("/nonexistent/path/xyz"))
        assert result == []

    def test_with_reports(self):
        with tempfile.TemporaryDirectory() as d:
            report = CompareReport(
                row_count=RowCountResult("t1", 100, "t2", 110, 10, 10.0),
            )
            p = Path(d) / "compare_20240101_120000.json"
            p.write_text(json.dumps(report.to_dict()), encoding="utf-8")
            result = build_trend_data(Path(d))
            assert len(result) == 1
            assert result[0]["delta"] == 10
            assert result[0]["delta_pct"] == 10.0

    def test_malformed_file_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "compare_bad.json"
            p.write_text("not json!!!", encoding="utf-8")
            result = build_trend_data(Path(d))
            assert result == []


class TestReportBatchFullSerialization:
    """Test that CompareReport round-trips with batch_full field."""

    def test_round_trip(self):
        schema = SchemaDiffResult("t1", "t1")
        rc = RowCountResult("t1", 10, "t1", 10, 0, 0.0)
        items = [BatchFullItem("t1", "t1", schema=schema, row_count=rc, has_diffs=False)]
        report = CompareReport(batch_full=items)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.batch_full is not None
        assert len(restored.batch_full) == 1
        assert restored.batch_full[0].table_a == "t1"
        assert restored.batch_full[0].has_diffs is False


class TestI18nRound4:
    """Test that all round-4 i18n keys are present in both languages."""

    ROUND4_KEYS = [
        "dc_preset_save", "dc_preset_load", "dc_preset_name",
        "dc_preset_saved", "dc_preset_deleted", "dc_preset_no_presets", "dc_presets",
        "dc_threshold", "dc_threshold_hint", "dc_threshold_pass", "dc_threshold_fail",
        "dc_gen_sync", "dc_sync_generated",
        "dc_col_mapping", "dc_col_mapping_hint",
        "dc_schedule", "dc_schedule_interval", "dc_schedule_start", "dc_schedule_stop",
        "dc_schedule_running", "dc_schedule_stopped",
        "dc_batch_full", "dc_batch_full_result", "dc_batch_summary",
        "dc_sample_strategy",
        "dc_trend", "dc_trend_chart", "dc_trend_no_data",
        "dc_history_count",
    ]

    def test_all_keys_present(self):
        for lang in ("en", "zh"):
            for key in self.ROUND4_KEYS:
                val = dc(lang, key)
                assert val != key, f"Missing i18n key {key!r} for lang={lang}"


# ── Round 5 Tests ──


class TestBuildIncrementalSql:
    """Tests for build_incremental_sql()."""

    def test_basic(self):
        sql = build_incremental_sql("orders", "updated_at", "2024-01-01")
        assert "updated_at" in sql
        assert "2024-01-01" in sql
        assert "orders" in sql

    def test_empty_last_value(self):
        sql = build_incremental_sql("orders", "updated_at", "")
        before_order = sql.split("ORDER")[0]
        assert ">" not in before_order

    def test_with_where(self):
        sql = build_incremental_sql("t", "ts", "100", where="status=1")
        assert "status=1" in sql

    def test_limit(self):
        sql = build_incremental_sql("t", "ts", "0", limit=50)
        assert "50" in sql

    def test_returns_string(self):
        result = build_incremental_sql("t", "col", "val")
        assert isinstance(result, str)


class TestParseQualityRules:
    """Tests for parse_quality_rules()."""

    def test_not_null_rule(self):
        rules = parse_quality_rules("name:not_null>95")
        assert len(rules) == 1
        assert rules[0].column == "name"
        assert rules[0].rule_type == "not_null_rate"

    def test_range_rule(self):
        rules = parse_quality_rules("age:range:0-150")
        assert len(rules) == 1
        assert rules[0].rule_type == "value_range"

    def test_unique_rule(self):
        rules = parse_quality_rules("id:unique>99")
        assert len(rules) == 1
        assert rules[0].rule_type == "unique_rate"

    def test_multiple_rules(self):
        rules = parse_quality_rules("name:not_null>95, id:unique>99")
        assert len(rules) == 2

    def test_empty_string(self):
        rules = parse_quality_rules("")
        assert rules == []


class TestCheckQualityRules:
    """Tests for check_quality_rules()."""

    def test_not_null_pass(self):
        rule = QualityRule(column="name", rule_type="not_null_rate", threshold=90.0)
        profile = ProfileResult(
            table_a="t1", table_b="t2", total_a=100, total_b=100,
            items=[ProfileItem(column="name", distinct_a=50, distinct_b=50,
                               null_rate_a=5.0, null_rate_b=5.0)])
        results = check_quality_rules([rule], profile)
        assert len(results) == 1
        assert results[0].passed is True

    def test_not_null_fail(self):
        rule = QualityRule(column="name", rule_type="not_null_rate", threshold=99.0)
        profile = ProfileResult(
            table_a="t1", table_b="t2", total_a=100, total_b=100,
            items=[ProfileItem(column="name", distinct_a=50, distinct_b=50,
                               null_rate_a=50.0, null_rate_b=50.0)])
        results = check_quality_rules([rule], profile)
        assert len(results) == 1
        assert results[0].passed is False

    def test_missing_column(self):
        rule = QualityRule(column="nonexistent", rule_type="not_null_rate", threshold=90.0)
        profile = ProfileResult(table_a="t1", table_b="t2")
        results = check_quality_rules([rule], profile)
        assert len(results) == 1
        assert results[0].passed is False


class TestGenerateDiffSql:
    """Tests for generate_diff_sql()."""

    def test_added_rows(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "name"],
            added=[(1, "a"), (2, "b")], removed=[], modified=[])
        sql = generate_diff_sql(diff, "target_table")
        assert "INSERT" in sql.upper()
        assert "target_table" in sql

    def test_removed_rows(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "name"],
            added=[], removed=[(3, "c")], modified=[])
        sql = generate_diff_sql(diff, "target_table")
        assert "DELETE" in sql.upper()
        assert "target_table" in sql

    def test_modified_rows(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "name"],
            added=[], removed=[],
            modified=[ModifiedRow(key=(1,), changes=[("name", "old", "new")])])
        sql = generate_diff_sql(diff, "target_table")
        assert "UPDATE" in sql.upper()
        assert "target_table" in sql

    def test_empty_diff(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id"],
            added=[], removed=[], modified=[])
        sql = generate_diff_sql(diff, "target_table")
        assert sql.strip() == ""

    def test_returns_string(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id"],
            added=[(1,)], removed=[], modified=[])
        assert isinstance(generate_diff_sql(diff, "t"), str)


class TestBuildDiffSqlCard:
    """Tests for build_diff_sql_card()."""

    def test_with_sql(self):
        html = build_diff_sql_card("INSERT INTO t VALUES (1);")
        assert "INSERT" in html
        assert "<pre" in html

    def test_empty_sql(self):
        html = build_diff_sql_card("")
        assert "no" in html.lower() or "dc_diff_sql_no_diff" in html


class TestComparisonTemplatesStore:
    """Tests for ComparisonTemplatesStore."""

    def test_save_and_list(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        store.save(name="test1", table_a="t1", table_b="t2")
        items = store.list()
        assert len(items) == 1
        assert items[0]["name"] == "test1"

    def test_get_by_name(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        store.save(name="test1", table_a="a", table_b="b")
        found = store.get_by_name("test1")
        assert found is not None
        assert found["table_a"] == "a"

    def test_delete(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        entry = store.save(name="test1", table_a="a", table_b="b")
        assert store.delete(entry["id"]) is True
        assert store.list() == []

    def test_upsert_by_name(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        store.save(name="t1", table_a="a", table_b="b")
        store.save(name="t1", table_a="c", table_b="d")
        items = store.list()
        assert len(items) == 1
        assert items[0]["table_a"] == "c"

    def test_max_entries(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        for i in range(105):
            store.save(name=f"t_{i}", table_a="a", table_b="b")
        assert len(store.list()) == 100


class TestSendWebhook:
    """Tests for _send_webhook() with mocked HTTP."""

    def test_success(self, monkeypatch):
        import urllib.request
        class MockResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b""
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: MockResp())
        ok, msg = _send_webhook("https://example.com/hook", {"key": "val"})
        assert ok is True

    def test_failure(self, monkeypatch):
        import urllib.request
        import urllib.error
        def fail(*a, **kw):
            raise urllib.error.URLError("connection refused")
        monkeypatch.setattr(urllib.request, "urlopen", fail)
        ok, msg = _send_webhook("https://example.com/hook", {"key": "val"})
        assert ok is False
        assert "refused" in msg

    def test_payload_json(self, monkeypatch):
        import urllib.request
        captured = {}
        class MockResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b""
        def capture(req, **kw):
            captured["data"] = req.data
            return MockResp()
        monkeypatch.setattr(urllib.request, "urlopen", capture)
        _send_webhook("https://example.com/hook", {"x": 1})
        assert b'"x"' in captured["data"]


class TestDrillDownCard:
    """Tests for drill-down in build_keyed_diff_card()."""

    def test_drill_down_present(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "name"],
            added=[], removed=[],
            modified=[ModifiedRow(key=(1,), changes=[("name", "old", "new")],
                                  row_a=(1, "old"), row_b=(1, "new"))])
        html = build_keyed_diff_card(diff, "en")
        assert "<details" in html

    def test_no_drill_down_without_rows(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "name"],
            added=[], removed=[],
            modified=[ModifiedRow(key=(1,), changes=[("name", "old", "new")])])
        html = build_keyed_diff_card(diff, "en")
        assert "Row A" not in html

    def test_empty_diff_card(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id"],
            added=[], removed=[], modified=[])
        html = build_keyed_diff_card(diff, "en")
        assert "no diff" in html.lower() or "identical" in html.lower()


class TestDetectSensitiveColumns:
    """Tests for detect_sensitive_columns()."""

    def test_email_detection(self):
        cols = ["id", "email"]
        rows = [(1, "user@example.com"), (2, "test@test.org")]
        result = detect_sensitive_columns(cols, rows)
        assert "email" in result

    def test_phone_detection(self):
        cols = ["id", "phone"]
        rows = [(1, "13800138000"), (2, "15912345678")]
        result = detect_sensitive_columns(cols, rows)
        assert "phone" in result

    def test_no_sensitive(self):
        cols = ["id", "count"]
        rows = [(1, 42), (2, 99)]
        result = detect_sensitive_columns(cols, rows)
        assert len(result) == 0

    def test_credit_card(self):
        cols = ["card"]
        rows = [("4111111111111111",), ("5500000000000004",)]
        result = detect_sensitive_columns(cols, rows)
        assert "card" in result

    def test_empty_rows(self):
        cols = ["email"]
        result = detect_sensitive_columns(cols, [])
        assert len(result) == 0


class TestMaskValue:
    """Tests for mask_value()."""

    def test_email_mask(self):
        result = mask_value("user@example.com", "email")
        assert "@" in result
        assert "user@example.com" != result

    def test_phone_mask(self):
        result = mask_value("13800138000", "phone")
        assert "****" in result or "13800138000" != result

    def test_none_value(self):
        result = mask_value(None, "email")
        assert result is not None


class TestMaskRows:
    """Tests for mask_rows()."""

    def test_basic_masking(self):
        cols = ["id", "email"]
        rows = [(1, "user@example.com")]
        sens = {"email": "email"}
        masked = mask_rows(cols, rows, sens)
        assert len(masked) == 1
        assert masked[0][1] != "user@example.com"

    def test_no_sensitive(self):
        cols = ["id", "name"]
        rows = [(1, "Alice")]
        masked = mask_rows(cols, rows, {})
        assert masked == [(1, "Alice")]

    def test_preserves_non_sensitive(self):
        cols = ["id", "email"]
        rows = [(42, "a@b.com")]
        sens = {"email": "email"}
        masked = mask_rows(cols, rows, sens)
        assert masked[0][0] == 42


class TestBuildQualityCard:
    """Tests for build_quality_card()."""

    def test_pass_result(self):
        results = [QualityResult(
            rule=QualityRule(column="name", rule_type="not_null", threshold=90.0),
            actual_value=95.0, passed=True)]
        html = build_quality_card(results, "en")
        assert "PASS" in html

    def test_fail_result(self):
        results = [QualityResult(
            rule=QualityRule(column="name", rule_type="not_null", threshold=99.0),
            actual_value=50.0, passed=False)]
        html = build_quality_card(results, "en")
        assert "FAIL" in html

    def test_empty(self):
        html = build_quality_card([], "en")
        assert html == ""


class TestI18nRound5:
    """Test that all round-5 i18n keys are present in both languages."""

    ROUND5_KEYS = [
        "dc_incremental", "dc_watermark_col", "dc_watermark_hint",
        "dc_watermark_value", "dc_incremental_compare",
        "dc_quality", "dc_quality_rules", "dc_quality_rules_hint",
        "dc_quality_check", "dc_quality_result", "dc_quality_pass", "dc_quality_fail",
        "dc_gen_diff_sql", "dc_diff_sql_result",
        "dc_diff_sql_no_diff",
        "dc_templates", "dc_template_save", "dc_template_load",
        "dc_template_name", "dc_template_saved", "dc_template_deleted",
        "dc_template_no_templates",
        "dc_webhook", "dc_webhook_url", "dc_webhook_url_hint",
        "dc_webhook_on_fail",
        "dc_drill_down", "dc_row_values_a", "dc_row_values_b",
        "dc_masking_enabled",
        "dc_environment", "dc_env_hint", "dc_compare_envs", "dc_env_a", "dc_env_b",
    ]

    def test_all_keys_present(self):
        for lang in ("en", "zh"):
            for key in self.ROUND5_KEYS:
                val = dc(lang, key)
                assert val != key, f"Missing i18n key {key!r} for lang={lang}"


# ── Code quality round: additional coverage ──


class TestSqlLiteral:
    """Tests for _sql_literal()."""

    def test_none(self):
        assert _sql_literal(None) == "NULL"

    def test_int(self):
        assert _sql_literal(42) == "42"

    def test_float(self):
        assert _sql_literal(3.14) == "3.14"

    def test_string(self):
        assert _sql_literal("hello") == "'hello'"

    def test_string_with_single_quote(self):
        assert _sql_literal("it's") == "'it''s'"

    def test_zero(self):
        assert _sql_literal(0) == "0"


class TestMaskValueExtended:
    """Tests for mask_value with id_number and credit_card types."""

    def test_id_number_mask(self):
        result = mask_value("110101199001011234", "id_number")
        assert result.startswith("110")
        assert result.endswith("1234")
        assert "*" in result

    def test_credit_card_mask(self):
        result = mask_value("4111111111111111", "credit_card")
        assert result.endswith("1111")
        assert "****" in result

    def test_credit_card_with_dashes(self):
        result = mask_value("4111-1111-1111-1111", "credit_card")
        assert result.endswith("1111")

    def test_short_id_falls_back(self):
        result = mask_value("123", "id_number")
        assert result == "***"

    def test_short_credit_card_falls_back(self):
        result = mask_value("12", "credit_card")
        assert result == "***"


class TestConnectionPresetEnvironment:
    """Tests for the environment field on ConnectionPresetsStore round-trip."""

    def test_save_with_environment(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            entry = store.save(
                "prod_conn", "mysql", "prod-host", 3306, "proddb",
                environment="production",
            )
            assert entry["environment"] == "production"
            items = store.list()
            assert items[0]["environment"] == "production"
        finally:
            os.unlink(path)

    def test_environment_defaults_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            entry = store.save("c1", "mysql", "h", 3306, "d")
            assert entry["environment"] == ""
        finally:
            os.unlink(path)


class TestParseQualityRulesEdgeCases:
    """Tests for parse_quality_rules with malformed input."""

    def test_garbage_string(self):
        rules = parse_quality_rules("not a rule at all")
        assert isinstance(rules, list)

    def test_missing_threshold(self):
        rules = parse_quality_rules("name:not_null")
        assert isinstance(rules, list)

    def test_whitespace_only(self):
        rules = parse_quality_rules("   ")
        assert rules == []

    def test_extra_commas(self):
        rules = parse_quality_rules(",,,name:not_null>95,,,")
        valid = [r for r in rules if r.column == "name"]
        assert len(valid) >= 1


class TestGenerateDiffSqlDsType:
    """Tests for generate_diff_sql with different ds_type values."""

    def test_default_mysql(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "val"],
            added=[(1, "x")], removed=[], modified=[])
        sql = generate_diff_sql(diff, "t1", ds_type="mysql")
        assert "INSERT" in sql.upper()

    def test_postgresql(self):
        diff = KeyedDiffResult(
            key_columns=["id"], columns=["id", "val"],
            added=[(1, "x")], removed=[], modified=[])
        sql = generate_diff_sql(diff, "t1", ds_type="postgresql")
        assert "INSERT" in sql.upper()


class TestTemplatesStoreGetByNameNone:
    """Explicit test for get_by_name returning None."""

    def test_returns_none_for_missing(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        store.save(name="existing", table_a="a", table_b="b")
        assert store.get_by_name("nonexistent") is None

    def test_returns_none_empty_store(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "tmpl.json")
        assert store.get_by_name("anything") is None


class TestWebhookTimeout:
    """Tests for _send_webhook timeout handling."""

    def test_timeout_error(self, monkeypatch):
        import urllib.request
        import socket
        def timeout(*a, **kw):
            raise socket.timeout("timed out")
        monkeypatch.setattr(urllib.request, "urlopen", timeout)
        ok, msg = _send_webhook("https://example.com/hook", {"k": "v"})
        assert ok is False

    def test_http_error(self, monkeypatch):
        import urllib.request
        import urllib.error
        def err(*a, **kw):
            raise urllib.error.HTTPError(
                "https://example.com", 500, "Server Error", {}, None)
        monkeypatch.setattr(urllib.request, "urlopen", err)
        ok, msg = _send_webhook("https://example.com/hook", {"k": "v"})
        assert ok is False


class TestStoreEmptyNameValidation:
    """Tests that stores reject empty names."""

    def test_presets_rejects_empty_name(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            with pytest.raises(ValueError, match="empty"):
                store.save("", "mysql", "h", 3306, "d")
        finally:
            os.unlink(path)

    def test_presets_rejects_whitespace_name(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            with pytest.raises(ValueError, match="empty"):
                store.save("   ", "mysql", "h", 3306, "d")
        finally:
            os.unlink(path)

    def test_templates_rejects_empty_name(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "t.json")
        with pytest.raises(ValueError, match="empty"):
            store.save(name="", table_a="a", table_b="b")

    def test_templates_rejects_whitespace_name(self, tmp_path):
        store = ComparisonTemplatesStore(tmp_path / "t.json")
        with pytest.raises(ValueError, match="empty"):
            store.save(name="  \t  ", table_a="a", table_b="b")


class TestPresetsStoreCorruptFile:
    """Tests for store handling of corrupt JSON files."""

    def test_corrupt_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8",
        ) as f:
            f.write("{{{invalid json")
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            assert store.list() == []
        finally:
            os.unlink(path)

    def test_save_overwrites_corrupt(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8",
        ) as f:
            f.write("not json!!!")
            path = f.name
        try:
            store = ConnectionPresetsStore(path)
            store.save("c1", "mysql", "h", 3306, "d")
            items = store.list()
            assert len(items) == 1
        finally:
            os.unlink(path)


# ===================================================================
# Bug regression tests  (code quality audit)
# ===================================================================


class TestFromDictNoMutation:
    """from_dict must not mutate its input dict."""

    def test_from_dict_preserves_input(self):
        data = {
            "schema": {
                "table_a": "t1", "table_b": "t2",
                "items": [{"column": "c", "status": "added", "type_a": "", "type_b": "INT"}],
                "cols_only_a": 0, "cols_only_b": 1, "type_changes": 0,
            },
            "aggregate": {
                "table_a": "t1", "table_b": "t2",
                "items": [{"column": "x", "metric": "sum",
                           "value_a": 1, "value_b": 2, "match": False}],
                "mismatches": 1,
            },
            "profile": {
                "table_a": "t1", "table_b": "t2", "total_a": 10, "total_b": 10,
                "items": [{"column": "c", "distinct_a": 5, "distinct_b": 5,
                           "null_rate_a": 0, "null_rate_b": 0,
                           "min_a": 1, "min_b": 1, "max_a": 10, "max_b": 10}],
            },
            "keyed_diff": {
                "key_columns": ["id"], "columns": ["id", "name"],
                "added": [(3, "c")], "removed": [],
                "modified": [{"key": [1], "changes": [["name", "a", "b"]],
                              "row_a": [1, "a"], "row_b": [1, "b"]}],
            },
            "elapsed_ms": 100,
        }
        original_schema_items_len = len(data["schema"]["items"])
        original_agg_items_len = len(data["aggregate"]["items"])

        CompareReport.from_dict(data)

        assert len(data["schema"]["items"]) == original_schema_items_len
        assert len(data["aggregate"]["items"]) == original_agg_items_len
        assert "items" in data["schema"]
        assert "items" in data["aggregate"]
        assert "items" in data["profile"]
        assert "modified" in data["keyed_diff"]

    def test_from_dict_can_be_called_twice(self):
        data = {
            "schema": {
                "table_a": "t1", "table_b": "t2",
                "items": [{"column": "c", "status": "removed", "type_a": "INT", "type_b": ""}],
                "cols_only_a": 1, "cols_only_b": 0, "type_changes": 0,
            },
            "elapsed_ms": 50,
        }
        r1 = CompareReport.from_dict(data)
        r2 = CompareReport.from_dict(data)
        assert r1.schema.items[0].column == r2.schema.items[0].column


class TestDiffByKeySharedColumns:
    """diff_by_key added/removed tuples must align with shared columns."""

    def test_added_rows_match_shared_columns(self):
        cols_a = ["id", "name", "extra_a"]
        cols_b = ["id", "name", "extra_b"]
        rows_a = [(1, "alice", "ea")]
        rows_b = [(1, "alice", "eb"), (2, "bob", "eb2")]
        result = diff_by_key(cols_a, rows_a, cols_b, rows_b, ["id"])
        assert result.columns == ["id", "name"]
        assert len(result.added) == 1
        assert len(result.added[0]) == 2
        assert result.added[0] == (2, "bob")

    def test_removed_rows_match_shared_columns(self):
        cols_a = ["id", "val", "only_a"]
        cols_b = ["id", "val"]
        rows_a = [(1, 10, "x"), (2, 20, "y")]
        rows_b = [(1, 10,)]
        result = diff_by_key(cols_a, rows_a, cols_b, rows_b, ["id"])
        assert result.columns == ["id", "val"]
        assert len(result.removed) == 1
        assert len(result.removed[0]) == 2
        assert result.removed[0] == (2, 20)

    def test_generate_diff_sql_with_filtered_rows(self):
        cols_a = ["id", "name", "extra"]
        cols_b = ["id", "name", "other"]
        rows_a = [(1, "a", "x")]
        rows_b = [(2, "b", "o")]
        kd = diff_by_key(cols_a, rows_a, cols_b, rows_b, ["id"])
        sql = generate_diff_sql(kd, "target_tbl")
        assert "INSERT INTO target_tbl (id, name) VALUES (2, 'b');" in sql
        assert "DELETE FROM target_tbl WHERE id = 1;" in sql


class TestSqlLiteralEdgeCases:
    """_sql_literal must handle NaN, Inf, and special strings."""

    def test_nan_becomes_null(self):
        assert _sql_literal(float("nan")) == "NULL"

    def test_inf_becomes_null(self):
        assert _sql_literal(float("inf")) == "NULL"

    def test_neg_inf_becomes_null(self):
        assert _sql_literal(float("-inf")) == "NULL"

    def test_string_with_quotes(self):
        assert _sql_literal("it's") == "'it''s'"

    def test_none_is_null(self):
        assert _sql_literal(None) == "NULL"

    def test_int_passthrough(self):
        assert _sql_literal(42) == "42"


class TestQualityRulesNonNumeric:
    """check_quality_rules must not crash on non-numeric min/max values."""

    def test_string_min_a_does_not_crash(self):
        profile = ProfileResult(
            table_a="t1", table_b="t2", total_a=10, total_b=10,
            items=[ProfileItem(
                column="name", distinct_a=5, distinct_b=5,
                null_rate_a=0, null_rate_b=0,
                min_a="alice", min_b="alice", max_a="zoe", max_b="zoe",
            )],
        )
        rules = [QualityRule(column="name", rule_type="min_value", threshold=0)]
        results = check_quality_rules(rules, profile)
        assert len(results) == 1
        assert results[0].actual_value == 0.0
        assert results[0].passed is True

    def test_string_range_does_not_crash(self):
        profile = ProfileResult(
            table_a="t1", table_b="t2", total_a=10, total_b=10,
            items=[ProfileItem(
                column="status", distinct_a=3, distinct_b=3,
                min_a="active", max_a="pending",
            )],
        )
        rules = [QualityRule(column="status", rule_type="value_range",
                             min_val=0, max_val=100)]
        results = check_quality_rules(rules, profile)
        assert len(results) == 1


class TestBuildIncrementalSqlEscaping:
    """build_incremental_sql must safely handle special chars in last_value."""

    def test_quotes_in_value(self):
        sql = build_incremental_sql("orders", "ts", "2024-01-01 00:00:00")
        assert "'" in sql
        assert "ts" in sql.lower() or "TS" in sql

    def test_empty_last_value(self):
        sql = build_incremental_sql("orders", "updated_at", "")
        assert ">" not in sql


# =====================================================================
# BB — Data Skew
# =====================================================================


class TestComputeSkewMetrics:
    """Tests for compute_skew_metrics()."""

    def test_uniform(self):
        gini, cv, top1 = compute_skew_metrics([10, 10, 10, 10])
        assert gini == 0.0
        assert cv == 0.0
        assert top1 == 25.0

    def test_single_value(self):
        gini, cv, top1 = compute_skew_metrics([100])
        assert gini == 0.0
        assert top1 == 100.0

    def test_skewed(self):
        gini, cv, top1 = compute_skew_metrics([900, 50, 30, 10, 10])
        assert gini > 0.5
        assert cv > 1.0
        assert top1 == 90.0

    def test_empty(self):
        gini, cv, top1 = compute_skew_metrics([])
        assert gini == 0.0
        assert cv == 0.0
        assert top1 == 0.0


class TestBuildSkewSql:
    """Tests for build_skew_sql()."""

    def test_basic(self):
        sql = build_skew_sql("orders", "status")
        assert "status" in sql
        assert "orders" in sql
        assert "GROUP BY" in sql
        assert "ORDER BY" in sql

    def test_with_where(self):
        sql = build_skew_sql("t", "col", where="active=1")
        assert "active=1" in sql

    def test_identifier_quoting(self):
        sql = build_skew_sql("my table", "my col")
        assert "my table" in sql or '"my table"' in sql
        assert "my col" in sql or '"my col"' in sql


class TestCompareSkew:
    """Tests for compare_skew()."""

    def test_equal_sides(self):
        rows = [("a", 50), ("b", 30), ("c", 20)]
        item = compare_skew("t1", "t2", "status", rows, 100, rows, 100)
        assert item.column == "status"
        assert item.gini_a == item.gini_b
        assert item.cv_a == item.cv_b
        assert len(item.buckets) == 3

    def test_skewed_vs_uniform(self):
        rows_a = [("x", 900), ("y", 50), ("z", 50)]
        rows_b = [("x", 333), ("y", 333), ("z", 334)]
        item = compare_skew("t1", "t2", "col", rows_a, 1000, rows_b, 1000)
        assert item.gini_a > item.gini_b
        assert item.top1_pct_a > item.top1_pct_b

    def test_empty(self):
        item = compare_skew("t1", "t2", "col", [], 0, [], 0)
        assert item.gini_a == 0.0
        assert item.gini_b == 0.0
        assert len(item.buckets) == 0


class TestSkewDataclasses:
    """Tests for SkewBucket, SkewItem, SkewResult dataclasses."""

    def test_skew_bucket_defaults(self):
        b = SkewBucket(value="test")
        assert b.count_a == 0
        assert b.pct_a == 0.0

    def test_skew_item_fields(self):
        item = SkewItem(column="col1", gini_a=0.5, gini_b=0.3)
        assert item.column == "col1"
        assert item.gini_a == 0.5
        assert item.buckets == []


class TestBuildSkewCard:
    """Tests for build_skew_card()."""

    def test_empty_result(self):
        result = SkewResult("t1", "t2")
        html = build_skew_card(result, "en")
        assert "Skew" in html or "skew" in html.lower()

    def test_with_items(self):
        result = SkewResult(
            "t1", "t2", 100, 200,
            items=[SkewItem(
                column="status", gini_a=0.3, gini_b=0.4,
                cv_a=1.0, cv_b=1.2,
                top1_pct_a=40.0, top1_pct_b=50.0,
                ndv_a=5, ndv_b=6,
                buckets=[SkewBucket("active", 60, 100, 60.0, 50.0)],
            )],
        )
        html = build_skew_card(result, "en")
        assert "status" in html
        assert "active" in html
        assert "0.3" in html

    def test_gini_warning(self):
        result = SkewResult(
            "t1", "t2", 100, 100,
            items=[SkewItem(
                column="skewed_col", gini_a=0.8, gini_b=0.2,
            )],
        )
        html = build_skew_card(result, "en")
        assert "dc2626" in html  # red warning color for gini > 0.6


class TestSkewFromDict:
    """Tests for CompareReport round-trip with skew data."""

    def test_round_trip(self):
        skew = SkewResult(
            "t1", "t2", 1000, 2000,
            items=[SkewItem(
                column="status", gini_a=0.5, gini_b=0.3,
                cv_a=1.2, cv_b=0.8,
                top1_pct_a=60.0, top1_pct_b=40.0,
                ndv_a=10, ndv_b=15,
                buckets=[SkewBucket("active", 600, 800, 60.0, 40.0)],
            )],
        )
        report = CompareReport(skew=skew)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.skew is not None
        assert restored.skew.table_a == "t1"
        assert len(restored.skew.items) == 1
        assert restored.skew.items[0].gini_a == 0.5
        assert len(restored.skew.items[0].buckets) == 1
        assert restored.skew.items[0].buckets[0].value == "active"

    def test_no_mutation(self):
        d = {
            "skew": {
                "table_a": "t1", "table_b": "t2",
                "total_a": 100, "total_b": 200,
                "items": [{"column": "c", "gini_a": 0.5, "gini_b": 0.3,
                           "cv_a": 0.0, "cv_b": 0.0,
                           "top1_pct_a": 0.0, "top1_pct_b": 0.0,
                           "ndv_a": 0, "ndv_b": 0,
                           "buckets": []}],
            }
        }
        original_items = len(d["skew"]["items"])
        CompareReport.from_dict(d)
        assert len(d["skew"]["items"]) == original_items


# ── Phase 1: Code Optimizations Tests ──


class TestRowLimit:
    """Tests for _row_limit() dialect helper."""

    def test_mysql_uses_limit(self):
        top, tail = _row_limit("mysql", 100)
        assert top == ""
        assert "LIMIT 100" in tail

    def test_sqlserver_uses_top(self):
        top, tail = _row_limit("sqlserver", 50)
        assert "TOP 50" in top
        assert tail == ""

    def test_hive_uses_limit(self):
        top, tail = _row_limit("hive", 200)
        assert top == ""
        assert "LIMIT 200" in tail

    def test_postgresql_uses_limit(self):
        top, tail = _row_limit("postgresql", 10)
        assert top == ""
        assert "LIMIT 10" in tail


class TestBuildSampleSqlDialect:
    """Tests for build_sample_sql with ds_type parameter."""

    def test_default_mysql(self):
        sql = build_sample_sql("t1", 100)
        assert "LIMIT 100" in sql
        assert "TOP" not in sql

    def test_sqlserver(self):
        sql = build_sample_sql("t1", 50, ds_type="sqlserver")
        assert "TOP 50" in sql
        assert "LIMIT" not in sql

    def test_where_with_sqlserver(self):
        sql = build_sample_sql("t1", 10, where="id > 5", ds_type="sqlserver")
        assert "TOP 10" in sql
        assert "WHERE id > 5" in sql
        assert "LIMIT" not in sql


class TestBuildIncrementalSqlDialect:
    """Tests for build_incremental_sql with ds_type parameter."""

    def test_default_mysql(self):
        sql = build_incremental_sql("t1", "ts", "2024-01-01")
        assert "LIMIT 1000" in sql
        assert "TOP" not in sql

    def test_sqlserver(self):
        sql = build_incremental_sql("t1", "ts", "2024-01-01", ds_type="sqlserver")
        assert "TOP 1000" in sql
        assert "LIMIT" not in sql


class TestBuildSkewSqlDialect:
    """Tests for build_skew_sql with ds_type parameter."""

    def test_default_mysql(self):
        sql = build_skew_sql("t1", "col1")
        assert "LIMIT 20" in sql
        assert "TOP" not in sql

    def test_sqlserver(self):
        sql = build_skew_sql("t1", "col1", ds_type="sqlserver")
        assert "TOP 20" in sql
        assert "LIMIT" not in sql

    def test_no_limit_when_top_n_zero(self):
        sql = build_skew_sql("t1", "col1", top_n=0)
        assert "LIMIT" not in sql
        assert "TOP" not in sql


class TestErrorHtml:
    """Tests for _error_html() helper."""

    def test_basic_error(self):
        html = _error_html("en", ValueError("test error"))
        assert "dc2626" in html
        assert "test error" in html
        assert "<div" in html

    def test_escapes_html(self):
        html = _error_html("en", ValueError("<script>alert(1)</script>"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_chinese_lang(self):
        html = _error_html("zh", ValueError("err"))
        assert "err" in html


# ── Phase 2: Integration Tests ──


class _MockConfig:
    """Minimal config for MockExecutor."""
    def __init__(self, ds_type="mysql"):
        self.ds_type = ds_type
        self.host = "localhost"
        self.port = 3306
        self.database = "testdb"
        self.username = "root"
        self.password = ""


class _MockExecutor:
    """Duck-type compatible executor for integration tests."""

    def __init__(self, ds_type="mysql", tables=None, schemas=None, run_results=None):
        self.config = _MockConfig(ds_type)
        self._tables = tables or []
        self._schemas = schemas or {}
        self._run_results = run_results or {}
        self._default_result = QueryResult(columns=[], rows=[], elapsed_ms=1, row_count=0)

    def show_tables(self):
        return list(self._tables)

    def test_connection(self):
        return True, f"{self.config.host}:{self.config.port}/{self.config.database}"

    def describe_table(self, table_name):
        return self._schemas.get(table_name, self._make_empty_schema(table_name))

    def run(self, sql, max_rows=1000):
        for key, result in self._run_results.items():
            if key in sql:
                return result
        return self._default_result

    @staticmethod
    def _make_empty_schema(name):
        from seatunnel_agent.text2sql.schema import TableSchema
        return TableSchema(database="testdb", name=name, columns=[])


class TestEndToEndCompareFlow:
    """Integration tests composing the full comparison pipeline."""

    def _make_executors(self):
        from seatunnel_agent.text2sql.schema import ColumnSchema, TableSchema
        schema_a = TableSchema(
            database="db", name="users_a",
            columns=[
                ColumnSchema(name="id", dtype="int"),
                ColumnSchema(name="name", dtype="varchar(100)"),
                ColumnSchema(name="age", dtype="int"),
            ],
        )
        schema_b = TableSchema(
            database="db", name="users_b",
            columns=[
                ColumnSchema(name="id", dtype="int"),
                ColumnSchema(name="name", dtype="varchar(100)"),
                ColumnSchema(name="age", dtype="int"),
            ],
        )
        run_results_a = {
            "COUNT(*)": QueryResult(["cnt"], [(1000,)], 10, 1),
            "SUM(": QueryResult(
                ["sum_id", "min_id", "max_id", "avg_id", "count_id",
                 "sum_age", "min_age", "max_age", "avg_age", "count_age"],
                [(50000, 1, 1000, 500, 1000, 35000, 18, 80, 35, 1000)],
                20, 1,
            ),
            "COUNT(DISTINCT": QueryResult(
                ["total", "ndv_id", "null_id", "min_id", "max_id",
                 "ndv_name", "null_name", "min_name", "max_name",
                 "ndv_age", "null_age", "min_age", "max_age"],
                [(1000, 1000, 0, "1", "1000", 900, 0, "Alice", "Zoe",
                  60, 0, "18", "80")],
                30, 1,
            ),
        }
        run_results_b = {
            "COUNT(*)": QueryResult(["cnt"], [(1000,)], 10, 1),
            "SUM(": QueryResult(
                ["sum_id", "min_id", "max_id", "avg_id", "count_id",
                 "sum_age", "min_age", "max_age", "avg_age", "count_age"],
                [(50000, 1, 1000, 500, 1000, 35000, 18, 80, 35, 1000)],
                20, 1,
            ),
            "COUNT(DISTINCT": QueryResult(
                ["total", "ndv_id", "null_id", "min_id", "max_id",
                 "ndv_name", "null_name", "min_name", "max_name",
                 "ndv_age", "null_age", "min_age", "max_age"],
                [(1000, 1000, 0, "1", "1000", 900, 0, "Alice", "Zoe",
                  60, 0, "18", "80")],
                30, 1,
            ),
        }
        ex_a = _MockExecutor(tables=["users_a"], schemas={"users_a": schema_a},
                             run_results=run_results_a)
        ex_b = _MockExecutor(tables=["users_b"], schemas={"users_b": schema_b},
                             run_results=run_results_b)
        return ex_a, ex_b

    def test_schema_compare_identical(self):
        ex_a, ex_b = self._make_executors()
        desc_a = ex_a.describe_table("users_a")
        desc_b = ex_b.describe_table("users_b")
        cols_a = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
        cols_b = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
        result = compare_schemas(cols_a, cols_b, "users_a", "users_b")
        assert not result.has_changes
        assert result.cols_only_a == 0
        assert result.cols_only_b == 0

    def test_count_compare_equal(self):
        ex_a, ex_b = self._make_executors()
        sql_a = build_count_sql("users_a")
        ra = ex_a.run(sql_a, max_rows=1)
        sql_b = build_count_sql("users_b")
        rb = ex_b.run(sql_b, max_rows=1)
        ca = int(ra.rows[0][0])
        cb = int(rb.rows[0][0])
        result = build_row_count_result("users_a", ca, "users_b", cb)
        assert result.delta == 0
        assert result.count_a == 1000

    def test_aggregate_compare_identical(self):
        ex_a, ex_b = self._make_executors()
        shared_numeric = ["id", "age"]
        sql_a = build_aggregate_sql("users_a", shared_numeric)
        sql_b = build_aggregate_sql("users_b", shared_numeric)
        row_a = ex_a.run(sql_a, max_rows=1).rows[0]
        row_b = ex_b.run(sql_b, max_rows=1).rows[0]
        result = compare_aggregates("users_a", row_a, "users_b", row_b, shared_numeric)
        assert result.mismatches == 0

    def test_profile_compare_identical(self):
        ex_a, ex_b = self._make_executors()
        shared_cols = ["id", "name", "age"]
        sql_a = build_profile_sql("users_a", shared_cols)
        sql_b = build_profile_sql("users_b", shared_cols)
        row_a = ex_a.run(sql_a, max_rows=1).rows[0]
        row_b = ex_b.run(sql_b, max_rows=1).rows[0]
        total_a = int(row_a[0])
        total_b = int(row_b[0])
        result = compare_profiles("users_a", row_a, total_a, "users_b", row_b, total_b, shared_cols)
        assert len(result.items) == 3

    def test_full_report_round_trip(self):
        ex_a, ex_b = self._make_executors()
        desc_a = ex_a.describe_table("users_a")
        desc_b = ex_b.describe_table("users_b")
        cols_a = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
        cols_b = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
        schema_result = compare_schemas(cols_a, cols_b, "users_a", "users_b")
        count_result = build_row_count_result("users_a", 1000, "users_b", 1000)
        report = CompareReport(schema=schema_result, row_count=count_result, elapsed_ms=100)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.schema is not None
        assert restored.row_count is not None
        assert restored.elapsed_ms == 100

    def test_card_builders_produce_html(self):
        schema_result = compare_schemas(
            [{"name": "id", "type": "int"}],
            [{"name": "id", "type": "int"}],
            "t1", "t2",
        )
        html = build_schema_diff_card(schema_result, "en")
        assert "<" in html

        count_result = build_row_count_result("t1", 100, "t2", 100)
        html = build_count_card(count_result, "en")
        assert "<" in html

        agg_result = AggregateResult("t1", "t2")
        html = build_aggregate_card(agg_result, "en")
        assert "<" in html

        profile_result = ProfileResult("t1", "t2")
        html = build_profile_card(profile_result, "en")
        assert "<" in html

        skew_result = SkewResult("t1", "t2")
        html = build_skew_card(skew_result, "en")
        assert "<" in html


class TestValidateWhereEdgeCases:
    """Extra validation tests for _validate_where."""

    def test_ddl_reject_drop(self):
        ok, msg = _validate_where("id > 0; DROP TABLE users", "en")
        assert not ok

    def test_ddl_reject_insert(self):
        ok, msg = _validate_where("INSERT INTO users VALUES(1)", "en")
        assert not ok

    def test_safe_clause(self):
        ok, msg = _validate_where("status = 'active' AND age > 18", "en")
        assert ok

    def test_empty_is_ok(self):
        ok, msg = _validate_where("", "en")
        assert ok


# ── Phase 3: Checksum + Partition Tests ──


class TestBuildChecksumSql:
    """Tests for build_checksum_sql."""

    def test_basic(self):
        sql = build_checksum_sql("orders", ["id", "amount"], "mysql")
        assert "orders" in sql
        assert "GROUP BY" in sql
        assert "seg" in sql.lower()

    def test_sqlserver(self):
        sql = build_checksum_sql("orders", ["id"], "sqlserver")
        assert "orders" in sql
        assert "CHECKSUM" in sql

    def test_with_where(self):
        sql = build_checksum_sql("t", ["c1"], "mysql", where="status='active'")
        assert "WHERE" in sql
        assert "status" in sql

    def test_segments_param(self):
        sql = build_checksum_sql("t", ["c1"], "mysql", segments=5)
        assert "5" in sql


class TestCompareChecksums:
    """Tests for compare_checksums."""

    def test_identical(self):
        rows = [(0, 100, "abc"), (1, 200, "def")]
        result = compare_checksums("t1", "t2", rows, rows)
        assert result.mismatch_count == 0
        assert result.match_count == 2

    def test_mismatch(self):
        rows_a = [(0, 100, "abc")]
        rows_b = [(0, 100, "xyz")]
        result = compare_checksums("t1", "t2", rows_a, rows_b)
        assert result.mismatch_count == 1
        assert not result.items[0].match

    def test_empty(self):
        result = compare_checksums("t1", "t2", [], [])
        assert result.match_count == 0
        assert result.mismatch_count == 0

    def test_extra_segment(self):
        rows_a = [(0, 100, "abc"), (1, 200, "def")]
        rows_b = [(0, 100, "abc")]
        result = compare_checksums("t1", "t2", rows_a, rows_b)
        assert result.mismatch_count == 1


class TestBuildChecksumCard:
    """Tests for build_checksum_card."""

    def test_empty(self):
        result = ChecksumResult("t1", "t2")
        html = build_checksum_card(result, "en")
        assert "Checksum" in html

    def test_with_items(self):
        result = ChecksumResult("t1", "t2",
            items=[ChecksumItem(0, "abc", "abc", True),
                   ChecksumItem(1, "xyz", "def", False)],
            match_count=1, mismatch_count=1)
        html = build_checksum_card(result, "en")
        assert "Mismatch" in html


class TestBuildPartitionCountSql:
    """Tests for build_partition_count_sql."""

    def test_basic(self):
        sql = build_partition_count_sql("orders", "region")
        assert "region" in sql
        assert "GROUP BY" in sql

    def test_with_where(self):
        sql = build_partition_count_sql("t", "dt", where="year=2024")
        assert "WHERE" in sql


class TestComparePartitions:
    """Tests for compare_partitions."""

    def test_identical(self):
        rows = [("US", 100), ("EU", 200)]
        result = compare_partitions("t1", "t2", "region", rows, rows)
        assert result.total_delta == 0
        assert len(result.items) == 2

    def test_delta(self):
        rows_a = [("US", 100)]
        rows_b = [("US", 80)]
        result = compare_partitions("t1", "t2", "region", rows_a, rows_b)
        assert result.total_delta == 20
        assert result.items[0].delta == 20

    def test_missing_partition(self):
        rows_a = [("US", 100), ("EU", 200)]
        rows_b = [("US", 100)]
        result = compare_partitions("t1", "t2", "region", rows_a, rows_b)
        assert result.total_delta == 200


class TestBuildPartitionCard:
    """Tests for build_partition_card."""

    def test_empty(self):
        result = PartitionResult("t1", "t2")
        html = build_partition_card(result, "en")
        assert "Partition" in html

    def test_with_items(self):
        result = PartitionResult("t1", "t2", "region",
            items=[PartitionCompareItem("US", 100, 80, 20, 25.0)])
        html = build_partition_card(result, "en")
        assert "US" in html
        assert "+20" in html


class TestChecksumFromDict:
    """Tests for CompareReport round-trip with checksum."""

    def test_round_trip(self):
        ck = ChecksumResult("t1", "t2",
            items=[ChecksumItem(0, "abc", "abc", True)],
            match_count=1)
        report = CompareReport(checksum=ck)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.checksum is not None
        assert restored.checksum.match_count == 1
        assert restored.checksum.items[0].match is True


class TestPartitionFromDict:
    """Tests for CompareReport round-trip with partition."""

    def test_round_trip(self):
        pt = PartitionResult("t1", "t2", "region",
            items=[PartitionCompareItem("US", 100, 80, 20, 25.0)],
            total_delta=20)
        report = CompareReport(partition=pt)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.partition is not None
        assert restored.partition.partition_column == "region"
        assert restored.partition.items[0].delta == 20


# ── Phase 4: Custom Aggregates + Stratified Sampling Tests ──


class TestParseCustomAggExpressions:
    """Tests for parse_custom_agg_expressions."""

    def test_basic(self):
        result = parse_custom_agg_expressions("total=COUNT(*)\navg_age=AVG(age)")
        assert len(result) == 2
        assert result[0] == ("total", "COUNT(*)")
        assert result[1] == ("avg_age", "AVG(age)")

    def test_skip_ddl(self):
        result = parse_custom_agg_expressions("bad=DROP TABLE foo")
        assert len(result) == 0

    def test_skip_comments(self):
        result = parse_custom_agg_expressions("# comment\ntotal=COUNT(*)")
        assert len(result) == 1

    def test_empty(self):
        result = parse_custom_agg_expressions("")
        assert result == []

    def test_no_equals(self):
        result = parse_custom_agg_expressions("no_equals_here")
        assert result == []


class TestBuildCustomAggSql:
    """Tests for build_custom_agg_sql."""

    def test_basic(self):
        sql = build_custom_agg_sql("orders", [("total", "COUNT(*)"), ("avg_amount", "AVG(amount)")])
        assert "COUNT(*)" in sql
        assert "AVG(amount)" in sql
        assert "orders" in sql

    def test_with_where(self):
        sql = build_custom_agg_sql("t", [("n", "COUNT(*)")], where="status='active'")
        assert "WHERE" in sql


class TestCompareCustomAggs:
    """Tests for compare_custom_aggs."""

    def test_identical(self):
        expressions = [("total", "COUNT(*)"), ("avg", "AVG(x)")]
        result = compare_custom_aggs("t1", (100, 5.0), "t2", (100, 5.0), expressions)
        assert result.mismatches == 0
        assert len(result.items) == 2

    def test_mismatch(self):
        expressions = [("total", "COUNT(*)")]
        result = compare_custom_aggs("t1", (100,), "t2", (200,), expressions)
        assert result.mismatches == 1
        assert not result.items[0].match

    def test_empty_rows(self):
        expressions = [("total", "COUNT(*)")]
        result = compare_custom_aggs("t1", (), "t2", (), expressions)
        assert result.items[0].value_a is None


class TestBuildCustomAggCard:
    """Tests for build_custom_agg_card."""

    def test_empty(self):
        result = CustomAggResult("t1", "t2")
        html = build_custom_agg_card(result, "en")
        assert "Custom" in html or "custom" in html.lower()

    def test_with_items(self):
        result = CustomAggResult("t1", "t2",
            items=[CustomAggItem("COUNT(*)", "total", 100, 100, True)])
        html = build_custom_agg_card(result, "en")
        assert "total" in html
        assert "COUNT(*)" in html


class TestCustomAggFromDict:
    """Tests for CompareReport round-trip with custom_agg."""

    def test_round_trip(self):
        ca = CustomAggResult("t1", "t2",
            items=[CustomAggItem("COUNT(*)", "total", 100, 100, True)],
            mismatches=0)
        report = CompareReport(custom_agg=ca)
        d = report.to_dict()
        restored = CompareReport.from_dict(d)
        assert restored.custom_agg is not None
        assert restored.custom_agg.items[0].alias == "total"


class TestI18nNewKeys:
    """Tests for new i18n keys in Phase 3+4."""

    def test_checksum_keys(self):
        from seatunnel_agent.data_comparison.i18n import DC_I18N
        for key in ["dc_checksum", "dc_checksum_result", "dc_checksum_segment",
                     "dc_checksum_match", "dc_checksum_mismatch", "dc_checksum_all_match"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"

    def test_partition_keys(self):
        from seatunnel_agent.data_comparison.i18n import DC_I18N
        for key in ["dc_partition", "dc_partition_result", "dc_partition_col",
                     "dc_partition_value", "dc_partition_delta"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"

    def test_custom_agg_keys(self):
        from seatunnel_agent.data_comparison.i18n import DC_I18N
        for key in ["dc_custom_agg", "dc_custom_agg_result", "dc_custom_agg_hint",
                     "dc_custom_agg_expression", "dc_custom_agg_alias"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"


class TestI18nSkew:
    """Verify all skew i18n keys exist."""

    SKEW_KEYS = [
        "dc_skew", "dc_skew_result", "dc_skew_column",
        "dc_skew_columns_hint", "dc_skew_analyze",
        "dc_skew_gini", "dc_skew_cv", "dc_skew_top1",
        "dc_skew_ndv", "dc_skew_no_columns",
    ]

    def test_all_keys_present(self):
        for lang in ("en", "zh"):
            for key in self.SKEW_KEYS:
                val = dc(lang, key)
                assert val != key, f"Missing i18n key {key!r} for lang={lang}"


# ── Stratified Sampling Tests ──


class TestBuildStratifiedSampleSql:
    """Tests for build_stratified_sample_sql."""

    def test_basic(self):
        sql = build_stratified_sample_sql("orders", "region")
        assert "ROW_NUMBER()" in sql
        assert "PARTITION BY" in sql
        assert "region" in sql

    def test_sqlserver(self):
        sql = build_stratified_sample_sql("orders", "region", ds_type="sqlserver")
        assert "ROW_NUMBER()" in sql
        assert "_rn <= 10" in sql

    def test_custom_per_group(self):
        sql = build_stratified_sample_sql("t", "cat", sample_per_group=5)
        assert "_rn <= 5" in sql

    def test_with_where(self):
        sql = build_stratified_sample_sql("t", "cat", where="status='active'")
        assert "WHERE" in sql
        assert "status" in sql

    def test_stratified_i18n_keys(self):
        for key in ["dc_stratified_col", "dc_stratified_col_hint"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"


# ── Phase 5: Trend Alerting + Batch Orchestration Tests ──


class TestParseAlertRules:
    """Tests for parse_alert_rules."""

    def test_basic(self):
        rules = parse_alert_rules("delta>100:3")
        assert len(rules) == 1
        assert isinstance(rules[0], AlertRule)
        assert rules[0].metric == "delta"
        assert rules[0].threshold == 100.0
        assert rules[0].consecutive == 3

    def test_multiple(self):
        rules = parse_alert_rules("delta>100:3, mismatches>0:5")
        assert len(rules) == 2

    def test_newline_separated(self):
        rules = parse_alert_rules("delta>100:3\nmismatches>0:5")
        assert len(rules) == 2

    def test_skip_comments(self):
        rules = parse_alert_rules("# a comment\ndelta>100:3")
        assert len(rules) == 1

    def test_empty(self):
        rules = parse_alert_rules("")
        assert rules == []

    def test_invalid_format(self):
        rules = parse_alert_rules("not-valid")
        assert rules == []


class TestCheckTrendAlerts:
    """Tests for check_trend_alerts."""

    def test_triggered(self):
        data = [
            {"delta": 150, "delta_pct": 10, "mismatches": 0},
            {"delta": 200, "delta_pct": 15, "mismatches": 0},
            {"delta": 180, "delta_pct": 12, "mismatches": 0},
        ]
        rules = [AlertRule(metric="delta", threshold=100, consecutive=3)]
        alerts = check_trend_alerts(data, rules)
        assert len(alerts) == 1
        assert alerts[0].triggered is True
        assert alerts[0].consecutive_actual == 3

    def test_not_triggered(self):
        data = [
            {"delta": 50, "delta_pct": 5, "mismatches": 0},
            {"delta": 200, "delta_pct": 15, "mismatches": 0},
        ]
        rules = [AlertRule(metric="delta", threshold=100, consecutive=3)]
        alerts = check_trend_alerts(data, rules)
        assert alerts[0].triggered is False

    def test_empty_data(self):
        rules = [AlertRule(metric="delta", threshold=100, consecutive=1)]
        alerts = check_trend_alerts([], rules)
        assert alerts[0].triggered is False
        assert alerts[0].consecutive_actual == 0


class TestBuildTrendAlertCard:
    """Tests for build_trend_alert_card."""

    def test_empty(self):
        html = build_trend_alert_card([], "en")
        assert html == ""

    def test_with_alerts(self):
        alerts = [
            TrendAlert("delta", 100.0, 3, 3, True, 150.0),
            TrendAlert("mismatches", 0.0, 5, 2, False, 0.0),
        ]
        html = build_trend_alert_card(alerts, "en")
        assert "TRIGGERED" in html
        assert "OK" in html

    def test_zh_locale(self):
        alerts = [TrendAlert("delta", 100.0, 3, 3, True, 150.0)]
        html = build_trend_alert_card(alerts, "zh")
        assert "已触发" in html


class TestBuildBatchTemplateCard:
    """Tests for build_batch_template_card."""

    def test_empty(self):
        html = build_batch_template_card([], "en")
        assert html == ""

    def test_with_results(self):
        results = [
            {"name": "tmpl1", "table_a": "t1", "table_b": "t2",
             "count_a": 100, "count_b": 100, "status": "pass"},
            {"name": "tmpl2", "table_a": "t3", "table_b": "t4",
             "count_a": 100, "count_b": 80, "status": "fail"},
        ]
        html = build_batch_template_card(results, "en")
        assert "tmpl1" in html
        assert "tmpl2" in html
        assert "Pass" in html
        assert "Fail" in html

    def test_with_error(self):
        results = [{"name": "bad", "status": "fail", "detail": "connection error"}]
        html = build_batch_template_card(results, "en")
        assert "connection error" in html


class TestI18nPhase5Keys:
    """Tests for new Phase 5 i18n keys."""

    def test_alert_keys(self):
        for key in ["dc_alert_rules", "dc_alert_rules_hint", "dc_alert_result",
                     "dc_alert_triggered", "dc_alert_ok", "dc_alert_metric",
                     "dc_alert_threshold", "dc_alert_consecutive"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"

    def test_batch_template_keys(self):
        for key in ["dc_batch_templates", "dc_batch_templates_hint",
                     "dc_batch_templates_run", "dc_batch_templates_result",
                     "dc_batch_templates_pass", "dc_batch_templates_fail"]:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"


# ── Phase 1: Safety Tests ──


class TestXssEscaping:
    """Verify XSS-prone card builders escape user-derived data."""

    def test_checksum_segment_escaped(self):
        item = ChecksumItem(
            segment='<script>alert(1)</script>',
            checksum_a="abc123abcdef1234", checksum_b="xyz789xyz789abcd",
            match=False,
        )
        result = ChecksumResult("t1", "t2", items=[item], mismatch_count=1)
        html = build_checksum_card(result)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_columns_added_escaped(self):
        diff = ResultDiff(
            added_rows=[(1,)], removed_rows=[],
            columns_added=['<img src=x onerror=alert(1)>'],
            columns_removed=['<b>bold</b>'],
        )
        html = build_sample_diff_card(diff)
        assert "<img src=" not in html
        assert "&lt;img" in html
        assert "<b>bold</b>" not in html

    def test_custom_agg_values_escaped(self):
        item = CustomAggItem(
            alias="a", expression="COUNT(*)",
            value_a='<script>x</script>', value_b="42", match=False,
        )
        result = CustomAggResult("t1", "t2", items=[item], mismatches=1)
        html = build_custom_agg_card(result)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_batch_template_tables_escaped(self):
        results = [{"name": "t", "table_a": '<img src=x>',
                     "table_b": '<script>y</script>', "status": "pass"}]
        html = build_batch_template_card(results)
        assert "<img src=" not in html
        assert "<script>" not in html


class TestSqlLiteralBackslash:
    """Verify _sql_literal escapes backslashes."""

    def test_backslash_escaped(self):
        result = _sql_literal("hello\\world")
        assert "\\\\" in result

    def test_single_quote_still_escaped(self):
        result = _sql_literal("it's")
        assert "''" in result

    def test_both_escapes(self):
        result = _sql_literal("a\\'b")
        assert "\\\\" in result
        assert "''" in result


class TestDdlKeywordsExpanded:
    """Verify expanded DDL/SQL blocklists catch new dangerous keywords."""

    def test_custom_agg_blocks_union(self):
        from seatunnel_agent.data_comparison.comparator import _CUSTOM_AGG_FORBIDDEN
        assert _CUSTOM_AGG_FORBIDDEN.search("SELECT 1 UNION SELECT 2")

    def test_custom_agg_blocks_semicolon(self):
        from seatunnel_agent.data_comparison.comparator import _CUSTOM_AGG_FORBIDDEN
        assert _CUSTOM_AGG_FORBIDDEN.search("COUNT(*); DROP TABLE x")

    def test_custom_agg_blocks_merge(self):
        from seatunnel_agent.data_comparison.comparator import _CUSTOM_AGG_FORBIDDEN
        assert _CUSTOM_AGG_FORBIDDEN.search("MERGE INTO t")

    def test_custom_agg_blocks_into_outfile(self):
        from seatunnel_agent.data_comparison.comparator import _CUSTOM_AGG_FORBIDDEN
        assert _CUSTOM_AGG_FORBIDDEN.search("SELECT * INTO OUTFILE '/tmp/x'")

    def test_custom_agg_allows_valid_agg(self):
        from seatunnel_agent.data_comparison.comparator import _CUSTOM_AGG_FORBIDDEN
        assert _CUSTOM_AGG_FORBIDDEN.search("SUM(amount)") is None

    def test_validate_where_blocks_union(self):
        ok, _ = _validate_where("1=1 UNION SELECT 1", "en")
        assert not ok

    def test_validate_where_blocks_merge(self):
        ok, _ = _validate_where("1=1; MERGE INTO t", "en")
        assert not ok


class TestHoconEscaping:
    """Verify _escape_hocon handles special characters."""

    def test_escape_double_quote(self):
        assert _escape_hocon('pass"word') == 'pass\\"word'

    def test_escape_backslash(self):
        assert _escape_hocon('a\\b') == 'a\\\\b'

    def test_escape_dollar(self):
        assert _escape_hocon('$var') == '$$var'

    def test_sync_config_escapes_password(self):
        config = generate_sync_config(
            "mysql", "h1", 3306, "db1", "user", 'p"a$$w\\rd', "t1",
            "mysql", "h2", 3306, "db2", "user2", "pwd2", "t2",
        )
        assert 'p\\"a$$$$w\\\\rd' in config


# ── Phase 2: Correctness Tests ──


class TestBuildChecksumSqlFixed:
    """Verify fixed checksum SQL has MIN(hash) and segments guard."""

    def test_uses_min_aggregate(self):
        sql = build_checksum_sql("orders", ["id", "amount"])
        assert "MIN(" in sql
        assert "GROUP BY" in sql

    def test_segments_zero_becomes_one(self):
        sql = build_checksum_sql("orders", ["id"], segments=0)
        assert "% 1" in sql or "MOD(" in sql

    def test_segments_negative_becomes_one(self):
        sql = build_checksum_sql("orders", ["id"], segments=-5)
        assert "% 1" in sql or "MOD(" in sql


class TestCheckAggregateThresholdFixed:
    """Verify check_aggregate_threshold now uses threshold parameter."""

    def test_none_threshold_uses_mismatch_count(self):
        result = AggregateResult("t1", "t2", items=[], mismatches=0)
        assert check_aggregate_threshold(result, None) is True
        result2 = AggregateResult("t1", "t2", items=[], mismatches=1)
        assert check_aggregate_threshold(result2, None) is False

    def test_absolute_threshold_within(self):
        items = [AggregateItem("col", "sum", value_a=100, value_b=102, match=False)]
        result = AggregateResult("t1", "t2", items=items, mismatches=1)
        threshold = ThresholdConfig(value=5.0, is_percentage=False)
        assert check_aggregate_threshold(result, threshold) is True

    def test_absolute_threshold_exceeded(self):
        items = [AggregateItem("col", "sum", value_a=100, value_b=110, match=False)]
        result = AggregateResult("t1", "t2", items=items, mismatches=1)
        threshold = ThresholdConfig(value=5.0, is_percentage=False)
        assert check_aggregate_threshold(result, threshold) is False

    def test_percentage_threshold_within(self):
        items = [AggregateItem("col", "avg", value_a=100, value_b=101, match=False)]
        result = AggregateResult("t1", "t2", items=items, mismatches=1)
        threshold = ThresholdConfig(value=5.0, is_percentage=True)
        assert check_aggregate_threshold(result, threshold) is True

    def test_percentage_threshold_exceeded(self):
        items = [AggregateItem("col", "avg", value_a=100, value_b=120, match=False)]
        result = AggregateResult("t1", "t2", items=items, mismatches=1)
        threshold = ThresholdConfig(value=5.0, is_percentage=True)
        assert check_aggregate_threshold(result, threshold) is False

    def test_none_values_skipped(self):
        items = [AggregateItem("col", "sum", value_a=None, value_b=100, match=False)]
        result = AggregateResult("t1", "t2", items=items, mismatches=1)
        threshold = ThresholdConfig(value=1.0, is_percentage=False)
        assert check_aggregate_threshold(result, threshold) is True


class TestStratifiedSqlFixed:
    """Verify stratified SQL no longer has arbitrary outer TOP/LIMIT."""

    def test_no_outer_limit(self):
        sql = build_stratified_sample_sql("users", "region", 10, "mysql")
        assert "TOP" not in sql.split("FROM")[0].split("(")[0]
        assert "LIMIT" not in sql.split("_rn")[1] if "_rn" in sql else True

    def test_has_rn_filter(self):
        sql = build_stratified_sample_sql("users", "region", 5)
        assert "_rn <= 5" in sql


# ── Phase 4: Edge Case Tests ──


class TestEdgeCases:
    """Missing edge case coverage identified by audit."""

    def test_parse_threshold_negative(self):
        t = parse_threshold("-5%")
        assert t is not None
        assert t.is_percentage is True
        assert t.value == -5.0

    def test_compute_skew_metrics_all_zeros(self):
        gini, cv, top1 = compute_skew_metrics([0, 0, 0])
        assert gini == 0.0
        assert cv == 0.0

    def test_mask_value_unknown_type(self):
        result = mask_value("hello", "unknown_type")
        assert isinstance(result, str)

    def test_detect_sensitive_columns_all_none(self):
        cols = ["name", "id"]
        rows = [(None, None), (None, None)]
        result = detect_sensitive_columns(cols, rows)
        assert isinstance(result, (list, dict, set))

    def test_compare_checksums_different_segment_counts(self):
        rows_a = [(0, 100, "abc123"), (1, 50, "def456")]
        rows_b = [(0, 100, "abc123")]
        result = compare_checksums("t1", "t2", rows_a, rows_b)
        assert result.mismatch_count >= 1

    def test_diff_by_key_duplicate_keys(self):
        cols_a = ["id", "name"]
        rows_a = [(1, "Alice"), (1, "Alice2")]
        cols_b = ["id", "name"]
        rows_b = [(1, "Alice")]
        result = diff_by_key(cols_a, rows_a, cols_b, rows_b, ["id"])
        assert result is not None


class TestDetailsCardHelper:
    """Verify the _details_card helper produces correct HTML."""

    def test_basic(self):
        from seatunnel_agent.data_comparison_ui import _details_card
        html = _details_card("<b>Title</b>", "<p>Body</p>")
        assert "<details open" in html
        assert "<b>Title</b>" in html
        assert "<p>Body</p>" in html
        assert "border:1px solid #e0e7ff" in html

    def test_custom_color(self):
        from seatunnel_agent.data_comparison_ui import _details_card
        html = _details_card("T", "B", border_color="#ff0000")
        assert "#ff0000" in html


class TestAlertRuleDataclass:
    """Verify AlertRule dataclass works correctly."""

    def test_create(self):
        rule = AlertRule(metric="delta", threshold=100.0, consecutive=3)
        assert rule.metric == "delta"
        assert rule.threshold == 100.0
        assert rule.consecutive == 3

    def test_parse_returns_alert_rules(self):
        rules = parse_alert_rules("delta>50:2, mismatches>0:1")
        assert all(isinstance(r, AlertRule) for r in rules)
        assert len(rules) == 2


# ── Phase 1: Engine Robustness tests ──────────────────────────────────────


class TestRunParallelPool:
    """Verify run_parallel reuses module-level pool."""

    def test_reuses_pool(self):
        r1 = run_parallel(lambda: 10, lambda: 20)
        r2 = run_parallel(lambda: 30, lambda: 40)
        assert r1 == (10, 20)
        assert r2 == (30, 40)

    def test_exception_propagation(self):
        def _boom():
            raise ValueError("bang")
        with pytest.raises(ValueError, match="bang"):
            run_parallel(_boom, lambda: 1)


class TestColumnTruncationWarning:
    """Verify warning logged when columns exceed 20."""

    def test_aggregate_sql_warns(self, caplog):
        cols = [f"col_{i}" for i in range(25)]
        import logging
        with caplog.at_level(logging.WARNING, logger="seatunnel_agent.data_comparison.comparator"):
            build_aggregate_sql("t1", cols)
        assert any("Truncating columns from 25 to 20" in r.message for r in caplog.records)

    def test_profile_sql_warns(self, caplog):
        cols = [f"col_{i}" for i in range(22)]
        import logging
        with caplog.at_level(logging.WARNING, logger="seatunnel_agent.data_comparison.comparator"):
            build_profile_sql("t1", cols)
        assert any("Truncating columns from 22 to 20" in r.message for r in caplog.records)

    def test_no_warning_under_20(self, caplog):
        cols = [f"col_{i}" for i in range(15)]
        import logging
        with caplog.at_level(logging.WARNING, logger="seatunnel_agent.data_comparison.comparator"):
            build_aggregate_sql("t1", cols)
            build_profile_sql("t1", cols)
        truncation_warnings = [r for r in caplog.records if "Truncating" in r.message]
        assert len(truncation_warnings) == 0

    def test_compare_aggregates_warns(self, caplog):
        cols = [f"col_{i}" for i in range(25)]
        row = tuple([100] + [0] * (25 * 5))
        import logging
        with caplog.at_level(logging.WARNING, logger="seatunnel_agent.data_comparison.comparator"):
            compare_aggregates("t1", row, "t2", row, cols)
        assert any("Truncating columns from 25 to 20" in r.message for r in caplog.records)

    def test_compare_profiles_warns(self, caplog):
        cols = [f"col_{i}" for i in range(21)]
        row = tuple([100] + [0] * (21 * 4))
        import logging
        with caplog.at_level(logging.WARNING, logger="seatunnel_agent.data_comparison.comparator"):
            compare_profiles("t1", row, 100, "t2", row, 100, cols)
        assert any("Truncating columns from 21 to 20" in r.message for r in caplog.records)


class TestCloseEnoughTolerance:
    """Verify configurable tolerance in _close_enough."""

    def test_default_tolerance_unchanged(self):
        assert _close_enough(1.0, 1.0) is True
        assert _close_enough(1.0, 1.0000001) is True
        assert _close_enough(1.0, 1.001) is False

    def test_custom_tolerance_passes(self):
        assert _close_enough(1.0, 1.005, tolerance=0.01) is True

    def test_custom_tolerance_fails(self):
        assert _close_enough(1.0, 1.02, tolerance=0.01) is False

    def test_none_handling_unchanged(self):
        assert _close_enough(None, None, tolerance=0.1) is True
        assert _close_enough(None, 1.0, tolerance=0.1) is False

    def test_compare_aggregates_tolerance(self):
        cols = ["amount"]
        row_a = (100, 1000.0, 100.0, 10.0, 500.0, 0)
        row_b = (100, 1005.0, 100.5, 10.0, 500.0, 0)
        result_strict = compare_aggregates("t1", row_a, "t2", row_b, cols, tolerance=1e-6)
        assert result_strict.mismatches > 0
        result_loose = compare_aggregates("t1", row_a, "t2", row_b, cols, tolerance=0.01)
        assert result_loose.mismatches == 0


class TestChecksumCaseNormalization:
    """Verify checksum comparison is case-insensitive."""

    def test_case_insensitive_match(self):
        rows_a = [(0, 100, "ABC123DEF")]
        rows_b = [(0, 100, "abc123def")]
        result = compare_checksums("t1", "t2", rows_a, rows_b)
        assert result.mismatch_count == 0
        assert result.match_count == 1

    def test_different_hashes_still_mismatch(self):
        rows_a = [(0, 100, "abc123")]
        rows_b = [(0, 100, "xyz789")]
        result = compare_checksums("t1", "t2", rows_a, rows_b)
        assert result.mismatch_count == 1


# ── Phase 2: Export completeness tests ────────────────────────────────────


class TestExportCSVCompleteness:
    """Verify CSV export includes all report sections."""

    def _make_full_report(self):
        return CompareReport(
            schema=SchemaDiffResult(
                table_a="t1", table_b="t2",
                items=[SchemaDiffItem(column="c1", type_a="INT", type_b="VARCHAR", status="modified")],
                type_changes=1,
            ),
            row_count=RowCountResult(table_a="t1", count_a=100, table_b="t2", count_b=95, delta=5, delta_pct=5.3),
            aggregate=AggregateResult(
                table_a="t1", table_b="t2",
                items=[AggregateItem(column="c1", metric="sum", value_a=100, value_b=95, match=False)],
                mismatches=1,
            ),
            profile=ProfileResult(
                table_a="t1", table_b="t2",
                items=[ProfileItem(column="c1", distinct_a=10, distinct_b=9,
                                   null_rate_a=1.0, null_rate_b=2.0,
                                   min_a="0", min_b="0", max_a="100", max_b="99")],
            ),
            skew=SkewResult(
                table_a="t1", table_b="t2", total_a=100, total_b=95,
                items=[SkewItem(column="c1", gini_a=0.5, gini_b=0.4,
                                cv_a=0.3, cv_b=0.2, top1_pct_a=20.0, top1_pct_b=15.0)],
            ),
            keyed_diff=KeyedDiffResult(
                key_columns=["id"], columns=["id", "val"],
                added=[(1, "a")], removed=[(2, "b")], modified=[],
            ),
            checksum=ChecksumResult(
                table_a="t1", table_b="t2",
                items=[ChecksumItem(segment=0, checksum_a="abc", checksum_b="abc", match=True)],
                match_count=1, mismatch_count=0,
            ),
            partition=PartitionResult(
                table_a="t1", table_b="t2", partition_column="dt",
                items=[PartitionCompareItem(partition_value="2024-01", count_a=50, count_b=48, delta=2)],
                total_delta=2,
            ),
            custom_agg=CustomAggResult(
                table_a="t1", table_b="t2",
                items=[CustomAggItem(expression="SUM(c1)", alias="total", value_a=100.0, value_b=95.0, match=False)],
                mismatches=1,
            ),
        )

    def test_skew_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "[Skew Analysis]" in content

    def test_keyed_diff_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "[Keyed Diff]" in content

    def test_checksum_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "[Checksum]" in content

    def test_partition_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "[Partition]" in content

    def test_custom_agg_section(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        assert "[Custom Aggregates]" in content

    def test_empty_report_no_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = CompareReport()
        path = _export_report_csv(report)
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Phase 3 — Trend data schema_changes, preset environment, batch template
# ---------------------------------------------------------------------------


class TestTrendDataSchemaChanges:
    """build_trend_data should include schema_changes field."""

    def test_schema_changes_extracted(self, tmp_path):
        report = CompareReport(
            schema=SchemaDiffResult(
                table_a="t1", table_b="t2",
                items=[SchemaDiffItem(column="c1", status="added", type_a="", type_b="INT")],
            ),
            row_count=RowCountResult(table_a="t1", count_a=10, table_b="t2", count_b=10,
                                     delta=0, delta_pct=0.0),
        )
        import json
        fpath = tmp_path / "compare_20240101_120000.json"
        with open(fpath, "w") as f:
            json.dump(report.to_dict(), f)
        entries = build_trend_data(tmp_path)
        assert len(entries) == 1
        assert entries[0]["schema_changes"] == 1

    def test_missing_schema_defaults_zero(self, tmp_path):
        report = CompareReport(
            row_count=RowCountResult(table_a="t1", count_a=10, table_b="t2", count_b=10,
                                     delta=0, delta_pct=0.0),
        )
        import json
        fpath = tmp_path / "compare_20240102_120000.json"
        with open(fpath, "w") as f:
            json.dump(report.to_dict(), f)
        entries = build_trend_data(tmp_path)
        assert len(entries) == 1
        assert entries[0]["schema_changes"] == 0


class TestSavePresetEnvironment:
    """_save_preset should pass environment to store."""

    def test_save_with_environment(self, tmp_path):
        store = ConnectionPresetsStore(tmp_path / "presets.json")
        store.save("test_preset", "mysql", "localhost", 3306, "db", "user", "pwd",
                   environment="staging")
        presets = store.list()
        assert len(presets) == 1
        assert presets[0]["environment"] == "staging"

    def test_save_without_environment(self, tmp_path):
        store = ConnectionPresetsStore(tmp_path / "presets.json")
        store.save("test_preset", "mysql", "localhost", 3306, "db", "user", "pwd")
        presets = store.list()
        assert len(presets) == 1
        assert presets[0].get("environment", "") == ""


class TestBatchTemplateCardSchemaAgg:
    """build_batch_template_card should display schema_changes and agg_mismatches."""

    def test_card_shows_schema_column(self):
        results = [{
            "name": "t1", "table_a": "a", "table_b": "b",
            "count_a": 100, "count_b": 100,
            "schema_changes": 2, "agg_mismatches": 1,
            "status": "fail",
        }]
        html = build_batch_template_card(results, "en")
        assert "Schema" in html
        assert "Agg Mismatches" in html
        assert ">2<" in html
        assert ">1<" in html

    def test_card_pass_with_no_issues(self):
        results = [{
            "name": "t1", "table_a": "a", "table_b": "b",
            "count_a": 100, "count_b": 100,
            "schema_changes": 0, "agg_mismatches": 0,
            "status": "pass",
        }]
        html = build_batch_template_card(results, "en")
        assert "Pass" in html


class TestPhase3I18nKeys:
    """All Phase 3 i18n keys exist in both EN and ZH."""

    PHASE3_KEYS = [
        "dc_env_compare_result",
        "dc_batch_tpl_schema",
        "dc_batch_tpl_agg",
        "dc_trend_mismatches",
        "dc_trend_schema",
        "dc_preset_env",
    ]

    def test_en_keys_present(self):
        for key in self.PHASE3_KEYS:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"

    def test_zh_keys_present(self):
        for key in self.PHASE3_KEYS:
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"

    def test_dc_function_returns_value(self):
        for key in self.PHASE3_KEYS:
            val = dc("en", key)
            assert val != key, f"dc() returned key itself for: {key}"


# ---------------------------------------------------------------------------
# Phase 4 — Password obfuscation, webhook summary
# ---------------------------------------------------------------------------


@pytest.fixture()
def _isolated_key(tmp_path, monkeypatch):
    """Point the encryption key file at tmp_path and clear the cached key."""
    from seatunnel_agent.data_comparison import presets as presets_mod
    key_path = tmp_path / "dc_secret.key"
    monkeypatch.setattr(presets_mod, "_KEY_PATH", key_path)
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    yield key_path
    presets_mod._cached_key = None


class TestPasswordEncryption:
    """Password encryption/decryption in presets."""

    def test_encrypt_roundtrip(self, _isolated_key):
        from seatunnel_agent.data_comparison.presets import _encrypt, _decrypt
        pwd = "s3cret!@#"
        encoded = _encrypt(pwd)
        assert encoded.startswith(("enc1:", "obf1:"))
        assert pwd not in encoded
        assert _decrypt(encoded) == pwd

    def test_empty_password(self, _isolated_key):
        from seatunnel_agent.data_comparison.presets import _encrypt, _decrypt
        assert _encrypt("") == ""
        assert _decrypt("") == ""

    def test_backward_compat_plain_password(self, _isolated_key):
        from seatunnel_agent.data_comparison.presets import _decrypt
        assert _decrypt("plain_password") == "plain_password"

    def test_backward_compat_b64_password(self, _isolated_key):
        import base64
        from seatunnel_agent.data_comparison.presets import _decrypt
        legacy = "b64:" + base64.b64encode(b"oldpwd").decode()
        assert _decrypt(legacy) == "oldpwd"

    def test_key_file_created(self, _isolated_key):
        from seatunnel_agent.data_comparison.presets import _encrypt
        _encrypt("x")
        assert _isolated_key.is_file()
        assert _isolated_key.read_bytes().strip()

    def test_corrupt_token_returns_empty(self, _isolated_key):
        from seatunnel_agent.data_comparison.presets import _decrypt
        assert _decrypt("enc1:not-a-valid-token") == ""

    def test_preset_password_stored_encrypted(self, _isolated_key, tmp_path):
        import json
        store = ConnectionPresetsStore(tmp_path / "presets.json")
        store.save("test", "mysql", "localhost", 3306, "db", "user", "secret123")
        raw = json.loads((tmp_path / "presets.json").read_text())
        assert raw[0]["password"].startswith(("enc1:", "obf1:"))
        assert "secret123" not in raw[0]["password"]

    def test_preset_password_loaded_clear(self, _isolated_key, tmp_path):
        store = ConnectionPresetsStore(tmp_path / "presets.json")
        store.save("test", "mysql", "localhost", 3306, "db", "user", "secret123")
        presets = store.list()
        assert presets[0]["password"] == "secret123"

    def test_get_by_name_decrypts(self, _isolated_key, tmp_path):
        store = ConnectionPresetsStore(tmp_path / "presets.json")
        store.save("test", "mysql", "localhost", 3306, "db", "user", "secret123")
        preset = store.get_by_name("test")
        assert preset["password"] == "secret123"

    def test_legacy_b64_auto_migrated_on_list(self, _isolated_key, tmp_path):
        import base64
        import json
        path = tmp_path / "presets.json"
        legacy_pwd = "b64:" + base64.b64encode(b"oldpwd").decode()
        path.write_text(json.dumps([{
            "id": "abc", "name": "old", "ds_type": "mysql",
            "host": "h", "port": 3306, "database": "d",
            "username": "u", "password": legacy_pwd,
        }]), encoding="utf-8")
        store = ConnectionPresetsStore(path)
        presets = store.list()
        assert presets[0]["password"] == "oldpwd"
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw[0]["password"].startswith(("enc1:", "obf1:"))

    def test_legacy_plaintext_auto_migrated_on_get(self, _isolated_key, tmp_path):
        import json
        path = tmp_path / "presets.json"
        path.write_text(json.dumps([{
            "id": "abc", "name": "old", "ds_type": "mysql",
            "host": "h", "port": 3306, "database": "d",
            "username": "u", "password": "plainpwd",
        }]), encoding="utf-8")
        store = ConnectionPresetsStore(path)
        preset = store.get_by_name("old")
        assert preset["password"] == "plainpwd"
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw[0]["password"].startswith(("enc1:", "obf1:"))


class TestWebhookSummary:
    """_build_webhook_summary should extract top-10 items."""

    def test_schema_diffs_capped(self):
        from seatunnel_agent.data_comparison_ui import _build_webhook_summary
        items = [
            SchemaDiffItem(column=f"c{i}", status="added", type_a="", type_b="INT")
            for i in range(15)
        ]
        report = CompareReport(
            schema=SchemaDiffResult(table_a="t1", table_b="t2", items=items),
        )
        summary = _build_webhook_summary(report)
        assert len(summary["schema_diffs"]) == 10

    def test_agg_mismatches_capped(self):
        from seatunnel_agent.data_comparison_ui import _build_webhook_summary
        items = [
            AggregateItem(column=f"c{i}", metric="sum",
                         value_a=float(i), value_b=float(i + 1), match=False)
            for i in range(15)
        ]
        report = CompareReport(
            aggregate=AggregateResult(
                table_a="t1", table_b="t2",
                items=items, mismatches=15,
            ),
        )
        summary = _build_webhook_summary(report)
        assert len(summary["agg_mismatches"]) == 10

    def test_no_diffs_returns_empty(self):
        from seatunnel_agent.data_comparison_ui import _build_webhook_summary
        report = CompareReport()
        summary = _build_webhook_summary(report)
        assert summary == {}


# ---------------------------------------------------------------------------
# Phase 5 — Report diff, expression rules, lineage
# ---------------------------------------------------------------------------


class TestDiffReports:
    """diff_reports should compare two CompareReport objects."""

    def test_no_changes(self):
        from seatunnel_agent.data_comparison.comparator import diff_reports, ReportDiff
        r1 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=10,
                                     delta=0, delta_pct=0.0),
        )
        r2 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=10,
                                     delta=0, delta_pct=0.0),
        )
        rdiff = diff_reports(r1, r2)
        assert not rdiff.has_changes

    def test_delta_change(self):
        from seatunnel_agent.data_comparison.comparator import diff_reports
        r1 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=10,
                                     delta=0, delta_pct=0.0),
        )
        r2 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=15,
                                     delta=5, delta_pct=50.0),
        )
        rdiff = diff_reports(r1, r2)
        assert rdiff.has_changes
        delta_item = next(i for i in rdiff.items if i.field == "delta")
        assert delta_item.old_value == 0
        assert delta_item.new_value == 5

    def test_aggregate_change(self):
        from seatunnel_agent.data_comparison.comparator import diff_reports
        r1 = CompareReport(
            aggregate=AggregateResult(table_a="t", table_b="t", items=[], mismatches=0),
        )
        r2 = CompareReport(
            aggregate=AggregateResult(table_a="t", table_b="t", items=[], mismatches=3),
        )
        rdiff = diff_reports(r1, r2)
        agg_item = next(i for i in rdiff.items if i.section == "aggregate")
        assert agg_item.changed
        assert agg_item.new_value == 3

    def test_none_sections(self):
        from seatunnel_agent.data_comparison.comparator import diff_reports
        r1 = CompareReport()
        r2 = CompareReport()
        rdiff = diff_reports(r1, r2)
        assert not rdiff.has_changes


class TestReportDiffCard:
    """build_report_diff_card should render HTML."""

    def test_card_with_changes(self):
        from seatunnel_agent.data_comparison.comparator import ReportDiff, ReportDiffItem
        rdiff = ReportDiff(items=[
            ReportDiffItem("row_count", "delta", 0, 5, True),
            ReportDiffItem("schema", "change_count", 0, 0, False),
        ])
        html = build_report_diff_card(rdiff, "en")
        assert "delta" in html
        assert "row_count" in html

    def test_card_no_changes(self):
        from seatunnel_agent.data_comparison.comparator import ReportDiff
        rdiff = ReportDiff(items=[])
        html = build_report_diff_card(rdiff, "en")
        assert "No changes" in html


class TestParseExpressionRule:
    """parse_quality_rules should handle expression rules."""

    def test_expression_rule_parsed(self):
        rules = parse_quality_rules("age:expr:age>0 AND age<150")
        assert len(rules) == 1
        assert rules[0].rule_type == "expression"
        assert rules[0].expression == "age>0 AND age<150"
        assert rules[0].column == "age"

    def test_expression_rule_pending(self):
        rules = parse_quality_rules("x:expr:x IS NOT NULL")
        profile = ProfileResult(table_a="t", table_b="t", items=[
            ProfileItem(column="x", distinct_a=5, distinct_b=5,
                        null_rate_a=0, null_rate_b=0,
                        min_a=1, max_a=100, min_b=1, max_b=100),
        ], total_a=100, total_b=100)
        results = check_quality_rules(rules, profile)
        assert len(results) == 1
        assert results[0].pending is True


class TestBuildExpressionCheckSql:
    """build_expression_check_sql generates correct SQL."""

    def test_basic(self):
        from seatunnel_agent.data_comparison.comparator import build_expression_check_sql
        sql = build_expression_check_sql("users", "age > 0")
        assert "SUM(CASE WHEN age > 0 THEN 1 ELSE 0 END)" in sql
        assert "COUNT(*)" in sql

    def test_with_where(self):
        from seatunnel_agent.data_comparison.comparator import build_expression_check_sql
        sql = build_expression_check_sql("users", "age > 0", "status = 'active'")
        assert "WHERE status = 'active'" in sql


class TestGetUpstreamTables:
    """get_upstream_tables should find source tables from SQL."""

    def test_basic(self):
        from seatunnel_agent.data_comparison.comparator import get_upstream_tables
        sqls = ["SELECT * FROM orders JOIN customers ON orders.cid = customers.id"]
        result = get_upstream_tables("orders", sqls)
        assert "customers" in result
        assert "orders" not in result

    def test_excludes_target(self):
        from seatunnel_agent.data_comparison.comparator import get_upstream_tables
        sqls = ["SELECT * FROM orders"]
        result = get_upstream_tables("orders", sqls)
        assert result == []


class TestLineageCard:
    """build_lineage_card renders HTML correctly."""

    def test_with_deps(self):
        html = build_lineage_card("target", ["src1", "src2"], "en")
        assert "src1" in html
        assert "src2" in html
        assert "Upstream" in html

    def test_no_deps(self):
        html = build_lineage_card("target", [], "en")
        assert "No upstream" in html


class TestPhase5I18nKeys:
    """All Phase 5 i18n keys exist in both EN and ZH."""

    PHASE5_KEYS = [
        "dc_report_diff", "dc_report_diff_result",
        "dc_report_diff_section", "dc_report_diff_field",
        "dc_report_diff_old_val", "dc_report_diff_new_val",
        "dc_report_diff_changed", "dc_report_diff_no_change",
        "dc_quality_expression", "dc_quality_expr_hint",
        "dc_lineage_title", "dc_lineage_hint", "dc_lineage_no_deps",
    ]

    def test_en_keys_present(self):
        for key in self.PHASE5_KEYS:
            assert key in DC_I18N["en"], f"Missing EN key: {key}"

    def test_zh_keys_present(self):
        for key in self.PHASE5_KEYS:
            assert key in DC_I18N["zh"], f"Missing ZH key: {key}"


# ---------------------------------------------------------------------------
# Phase 6 — Integration Tests + i18n Verification
# ---------------------------------------------------------------------------


class TestFullReportExportExcelAllSheets:
    """Excel export should have all sheet names."""

    def test_sheet_names(self, tmp_path, monkeypatch):
        from seatunnel_agent.data_comparison_ui import _export_report_excel
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = CompareReport(
            schema=SchemaDiffResult(
                table_a="t1", table_b="t2",
                items=[SchemaDiffItem(column="col1", status="added", type_a="", type_b="INT")],
            ),
            row_count=RowCountResult(table_a="t1", count_a=100, table_b="t2", count_b=100,
                                     delta=0, delta_pct=0.0),
            aggregate=AggregateResult(
                table_a="t1", table_b="t2",
                items=[AggregateItem(column="c1", metric="sum", value_a=10.0, value_b=10.0, match=True)],
                mismatches=0,
            ),
            profile=ProfileResult(
                table_a="t1", table_b="t2",
                items=[ProfileItem(column="c1", distinct_a=5, distinct_b=5,
                                   null_rate_a=0.0, null_rate_b=0.0,
                                   min_a=1, max_a=100, min_b=1, max_b=100)],
                total_a=100, total_b=100,
            ),
            skew=SkewResult(
                table_a="t1", table_b="t2", total_a=100, total_b=100,
                items=[SkewItem(column="c1", gini_a=0.1, gini_b=0.1,
                                cv_a=0.5, cv_b=0.5, top1_pct_a=5.0, top1_pct_b=5.0)],
            ),
            checksum=ChecksumResult(
                table_a="t1", table_b="t2",
                items=[ChecksumItem(segment="s1", checksum_a="abc", checksum_b="abc", match=True)],
                match_count=1, mismatch_count=0,
            ),
            partition=PartitionResult(
                table_a="t1", table_b="t2", partition_column="dt",
                items=[PartitionCompareItem(partition_value="p1", count_a=50, count_b=50, delta=0)],
                total_delta=0,
            ),
            custom_agg=CustomAggResult(
                table_a="t1", table_b="t2",
                items=[CustomAggItem(expression="SUM(x)", alias="sum_x",
                                      value_a=100, value_b=100, match=True)],
                mismatches=0,
            ),
        )
        path = _export_report_excel(report)
        assert path is not None
        assert Path(path).is_file()
        import openpyxl
        wb = openpyxl.load_workbook(path)
        expected = {"Schema Diff", "Row Count", "Aggregates", "Column Profile",
                    "Skew Analysis", "Checksum",
                    "Partition", "Custom Aggregates"}
        actual = set(wb.sheetnames)
        for name in expected:
            assert name in actual, f"Missing sheet: {name}"
        wb.close()
        os.unlink(path)


class TestReportDiffRealReports:
    """save→load→diff flow should work end-to-end."""

    def test_save_load_diff(self):
        from seatunnel_agent.data_comparison.comparator import diff_reports
        r1 = CompareReport(
            row_count=RowCountResult("t", 100, "t", 100, delta=0, delta_pct=0.0),
            aggregate=AggregateResult("t", "t", items=[], mismatches=0),
        )
        r2 = CompareReport(
            row_count=RowCountResult("t", 100, "t", 110, delta=10, delta_pct=10.0),
            aggregate=AggregateResult("t", "t", items=[], mismatches=2),
        )
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "r1.json"
            p2 = Path(td) / "r2.json"
            with open(p1, "w") as f:
                json.dump(r1.to_dict(), f)
            with open(p2, "w") as f:
                json.dump(r2.to_dict(), f)

            with open(p1) as f:
                loaded1 = CompareReport.from_dict(json.load(f))
            with open(p2) as f:
                loaded2 = CompareReport.from_dict(json.load(f))

            rdiff = diff_reports(loaded1, loaded2)
            assert rdiff.has_changes
            delta_item = next(i for i in rdiff.items if i.field == "delta")
            assert delta_item.old_value == 0
            assert delta_item.new_value == 10


class TestAllNewI18nKeysPresent:
    """Verify ALL new i18n keys from all phases are present."""

    ALL_NEW_KEYS = [
        # Phase 3
        "dc_env_compare_result", "dc_batch_tpl_schema", "dc_batch_tpl_agg",
        "dc_trend_mismatches", "dc_trend_schema", "dc_preset_env",
        # Phase 5
        "dc_report_diff", "dc_report_diff_result", "dc_report_old",
        "dc_report_new", "dc_report_compare", "dc_report_diff_section",
        "dc_report_diff_field", "dc_report_diff_old_val", "dc_report_diff_new_val",
        "dc_report_diff_changed", "dc_report_diff_no_change",
        "dc_quality_expression", "dc_quality_expr_hint",
        "dc_lineage_title", "dc_lineage_hint", "dc_lineage_no_deps",
    ]

    def test_en_all(self):
        for key in self.ALL_NEW_KEYS:
            assert key in DC_I18N["en"], f"Missing EN: {key}"

    def test_zh_all(self):
        for key in self.ALL_NEW_KEYS:
            assert key in DC_I18N["zh"], f"Missing ZH: {key}"


class TestEnZhParity:
    """EN and ZH dictionaries should have the same keys."""

    def test_same_key_count(self):
        en_keys = set(DC_I18N["en"].keys())
        zh_keys = set(DC_I18N["zh"].keys())
        missing_zh = en_keys - zh_keys
        missing_en = zh_keys - en_keys
        assert not missing_zh, f"Keys in EN but not ZH: {missing_zh}"
        assert not missing_en, f"Keys in ZH but not EN: {missing_en}"



# ---------------------------------------------------------------------------
# Phase 6 — Integration Tests + i18n Verification
# ---------------------------------------------------------------------------


class TestI18nParity:
    """EN and ZH should have exactly the same key set."""

    def test_en_zh_same_keys(self):
        en_keys = set(DC_I18N["en"].keys())
        zh_keys = set(DC_I18N["zh"].keys())
        missing_in_zh = en_keys - zh_keys
        missing_in_en = zh_keys - en_keys
        assert not missing_in_zh, f"Keys in EN but not ZH: {missing_in_zh}"
        assert not missing_in_en, f"Keys in ZH but not EN: {missing_in_en}"

    def test_no_empty_values(self):
        for lang in ("en", "zh"):
            for key, val in DC_I18N[lang].items():
                assert val, f"Empty value for {lang}:{key}"


class TestFullReportExportCSVAllSections:
    """Integration: a report with all fields exports all CSV sections."""

    def _make_full_report(self):
        return CompareReport(
            schema=SchemaDiffResult(
                table_a="t1", table_b="t2",
                items=[SchemaDiffItem(column="c1", type_a="INT", type_b="VARCHAR", status="modified")],
                type_changes=1,
            ),
            row_count=RowCountResult(table_a="t1", count_a=100, table_b="t2", count_b=95, delta=5, delta_pct=5.3),
            aggregate=AggregateResult(
                table_a="t1", table_b="t2",
                items=[AggregateItem(column="c1", metric="sum", value_a=100, value_b=95, match=False)],
                mismatches=1,
            ),
            profile=ProfileResult(
                table_a="t1", table_b="t2",
                items=[ProfileItem(column="c1", distinct_a=10, distinct_b=9,
                                   null_rate_a=1.0, null_rate_b=2.0,
                                   min_a="0", min_b="0", max_a="100", max_b="99")],
            ),
            skew=SkewResult(
                table_a="t1", table_b="t2", total_a=100, total_b=95,
                items=[SkewItem(column="c1", gini_a=0.5, gini_b=0.4,
                                cv_a=0.3, cv_b=0.2, top1_pct_a=20.0, top1_pct_b=15.0)],
            ),
            keyed_diff=KeyedDiffResult(
                key_columns=["id"], columns=["id", "val"],
                added=[(1, "a")], removed=[(2, "b")], modified=[],
            ),
            checksum=ChecksumResult(
                table_a="t1", table_b="t2",
                items=[ChecksumItem(segment=0, checksum_a="abc", checksum_b="abc", match=True)],
                match_count=1, mismatch_count=0,
            ),
            partition=PartitionResult(
                table_a="t1", table_b="t2", partition_column="dt",
                items=[PartitionCompareItem(partition_value="2024-01", count_a=50, count_b=48, delta=2)],
                total_delta=2,
            ),
            custom_agg=CustomAggResult(
                table_a="t1", table_b="t2",
                items=[CustomAggItem(expression="SUM(c1)", alias="total", value_a=100.0, value_b=95.0, match=False)],
                mismatches=1,
            ),
        )

    def test_all_csv_sections_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("seatunnel_agent.data_comparison_ui.default_desktop_dir", lambda: tmp_path)
        report = self._make_full_report()
        path = _export_report_csv(report)
        content = Path(path).read_text(encoding="utf-8-sig")
        for section in ["[Schema Diff]", "[Row Count]", "[Aggregates]", "[Column Profile]",
                        "[Skew Analysis]", "[Keyed Diff]", "[Checksum]",
                        "[Partition]", "[Custom Aggregates]"]:
            assert section in content, f"Missing section: {section}"


class TestReportDiffRoundtrip:
    """Integration: save→load→diff flow."""

    def test_save_load_diff(self, tmp_path):
        import json
        r1 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=10,
                                     delta=0, delta_pct=0.0),
            aggregate=AggregateResult(table_a="t", table_b="t", items=[], mismatches=0),
        )
        r2 = CompareReport(
            row_count=RowCountResult(table_a="t", count_a=10, table_b="t", count_b=15,
                                     delta=5, delta_pct=50.0),
            aggregate=AggregateResult(table_a="t", table_b="t", items=[], mismatches=2),
        )
        p1 = tmp_path / "report_old.json"
        p2 = tmp_path / "report_new.json"
        with open(p1, "w") as f:
            json.dump(r1.to_dict(), f)
        with open(p2, "w") as f:
            json.dump(r2.to_dict(), f)

        from seatunnel_agent.data_comparison.comparator import diff_reports
        loaded_old = CompareReport.from_dict(json.loads(p1.read_text()))
        loaded_new = CompareReport.from_dict(json.loads(p2.read_text()))
        rdiff = diff_reports(loaded_old, loaded_new)
        assert rdiff.has_changes
        delta_item = next(i for i in rdiff.items if i.field == "delta")
        assert delta_item.old_value == 0
        assert delta_item.new_value == 5


class TestTrendMultiMetric:
    """Integration: trend data includes all 3 metric fields."""

    def test_entries_have_all_fields(self, tmp_path):
        import json
        for i in range(3):
            r = CompareReport(
                row_count=RowCountResult(table_a="t", count_a=100+i, table_b="t", count_b=100,
                                         delta=i, delta_pct=float(i)),
                aggregate=AggregateResult(table_a="t", table_b="t", items=[], mismatches=i),
                schema=SchemaDiffResult(
                    table_a="t", table_b="t",
                    items=[SchemaDiffItem(column=f"c{j}", status="added", type_a="", type_b="INT")
                           for j in range(i)],
                ) if i > 0 else None,
            )
            fpath = tmp_path / f"compare_2024010{i}_120000.json"
            with open(fpath, "w") as f:
                json.dump(r.to_dict(), f)
        entries = build_trend_data(tmp_path)
        assert len(entries) == 3
        for e in entries:
            assert "delta" in e
            assert "mismatches" in e
            assert "schema_changes" in e
        assert entries[0]["schema_changes"] == 0
        assert entries[2]["schema_changes"] == 2


class TestWebhookPayloadStructure:
    """Webhook payload from _compare_all should have enhanced fields."""

    def test_build_webhook_summary_structure(self):
        from seatunnel_agent.data_comparison_ui import _build_webhook_summary
        report = CompareReport(
            schema=SchemaDiffResult(
                table_a="t1", table_b="t2",
                items=[SchemaDiffItem(column="c1", status="added", type_a="", type_b="INT")],
            ),
            aggregate=AggregateResult(
                table_a="t1", table_b="t2",
                items=[AggregateItem(column="c1", metric="sum", value_a=1, value_b=2, match=False)],
                mismatches=1,
            ),
        )
        summary = _build_webhook_summary(report)
        assert "schema_diffs" in summary
        assert len(summary["schema_diffs"]) == 1
        assert summary["schema_diffs"][0]["column"] == "c1"
        assert "agg_mismatches" in summary
        assert len(summary["agg_mismatches"]) == 1


# ---------------------------------------------------------------------------
# Dialect-aware SQL generation
# ---------------------------------------------------------------------------


class TestDialectQuoting:
    """quote_identifier / _sql_literal dialect behavior."""

    def test_mysql_backtick_quoting(self):
        from seatunnel_agent.data_comparison.comparator import quote_identifier
        assert quote_identifier("my col", "mysql") == "`my col`"

    def test_postgres_double_quote(self):
        from seatunnel_agent.data_comparison.comparator import quote_identifier
        assert quote_identifier("my col", "postgresql") == '"my col"'

    def test_default_double_quote_unchanged(self):
        from seatunnel_agent.data_comparison.comparator import quote_identifier
        assert quote_identifier("my col") == '"my col"'

    def test_safe_identifier_not_quoted(self):
        from seatunnel_agent.data_comparison.comparator import quote_identifier
        assert quote_identifier("orders", "mysql") == "orders"

    def test_backtick_escaped_in_backtick_dialect(self):
        from seatunnel_agent.data_comparison.comparator import quote_identifier
        assert quote_identifier("a`b", "mysql") == "`a``b`"

    def test_sql_literal_mysql_backslash_escaped(self):
        assert _sql_literal("a\\b", "mysql") == "'a\\\\b'"

    def test_sql_literal_postgres_backslash_kept(self):
        assert _sql_literal("a\\b", "postgresql") == "'a\\b'"

    def test_sql_literal_quote_doubled_everywhere(self):
        assert _sql_literal("o'brien", "postgresql") == "'o''brien'"
        assert _sql_literal("o'brien", "mysql") == "'o''brien'"


class TestDialectCastAndChecksum:
    """CAST/hash function selection per dialect."""

    def test_checksum_mysql_uses_crc32_and_char(self):
        sql = build_checksum_sql("orders", ["id"], "mysql")
        assert "CRC32" in sql
        assert "AS CHAR" in sql
        assert "VARCHAR(200)" not in sql

    def test_checksum_postgres_uses_hashtext(self):
        sql = build_checksum_sql("orders", ["id"], "postgresql")
        assert "HASHTEXT" in sql.upper()
        assert "CRC32" not in sql

    def test_checksum_sqlserver_uses_checksum(self):
        sql = build_checksum_sql("orders", ["id"], "sqlserver")
        assert "CHECKSUM" in sql
        assert "CRC32" not in sql

    def test_skew_sql_mysql_char_cast(self):
        sql = build_skew_sql("orders", "status", ds_type="mysql")
        assert "AS CHAR" in sql
        assert "VARCHAR(200)" not in sql

    def test_skew_sql_postgres_varchar_cast(self):
        sql = build_skew_sql("orders", "status", ds_type="postgresql")
        assert "VARCHAR(200)" in sql

    def test_partition_sql_mysql_char_cast(self):
        sql = build_partition_count_sql("orders", "region", ds_type="mysql")
        assert "AS CHAR" in sql

    def test_diff_sql_mysql_backtick_table(self):
        from seatunnel_agent.data_comparison.comparator import generate_diff_sql
        result = KeyedDiffResult(
            key_columns=["id"],
            columns=["id", "name"],
            added=[(1, "x")],
        )
        sql = generate_diff_sql(result, "my table", ds_type="mysql")
        assert "`my table`" in sql
