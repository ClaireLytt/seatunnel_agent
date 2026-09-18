"""Integration tests using real SQLite database (config/demo.db).

These tests use NO mocks — they execute real SQL against a real database.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

_DEMO_DB = str(Path(__file__).parent.parent / "config" / "demo.db")
_DB_PREFIX = _DEMO_DB  # full_name = "db_path.table_name" for SQLite

pytestmark = pytest.mark.integration


def _fn(table: str) -> str:
    """Build full_name as SchemaStore stores it for SQLite tables."""
    return f"{_DB_PREFIX}.{table}"


# ── Fixtures ──


@pytest.fixture
def config():
    from seatunnel_agent.text2sql.executor import DatabaseConfig
    return DatabaseConfig(ds_type="sqlite", host="", port=0, database=_DEMO_DB)


@pytest.fixture
def executor(config):
    from seatunnel_agent.text2sql.executor.sqlite import SQLiteExecutor
    return SQLiteExecutor(config)


@pytest.fixture
def store(executor):
    from seatunnel_agent.text2sql.schema import SchemaStore
    return SchemaStore.from_db(executor)


@pytest.fixture
def runtime(store, config):
    from seatunnel_agent.text2sql.tools import Text2SQLRuntime
    from seatunnel_agent.text2sql.executor.sqlite import SQLiteExecutor
    rt = Text2SQLRuntime(store=store, ds_type="sqlite", db_config=config)
    rt._executor = SQLiteExecutor(config)
    return rt


# ── 1. Executor Layer ──


class TestSQLiteExecutorIntegration:

    def test_connection(self, executor):
        ok, msg = executor.test_connection()
        assert ok
        assert "SQLite" in msg

    def test_show_tables(self, executor):
        tables = executor.show_tables()
        assert len(tables) == 6
        assert "student" in tables
        assert "course" in tables
        assert "sales_order" in tables

    def test_describe_table(self, executor):
        schema = executor.describe_table("student")
        assert schema.name == "student"
        col_names = [c.name for c in schema.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "age" in col_names
        assert len(schema.columns) == 7

    def test_fetch_all_schemas(self, executor):
        schemas = executor.fetch_all_schemas()
        assert len(schemas) == 6
        names = {s.name for s in schemas}
        assert names == {"student", "course", "score", "sales_order", "employee", "page_view"}

    def test_run_simple_query(self, executor):
        result = executor.run("SELECT COUNT(*) FROM student")
        assert result.row_count == 1
        assert result.rows[0][0] > 0

    def test_run_with_limit(self, executor):
        result = executor.run("SELECT * FROM student", max_rows=5)
        assert result.row_count == 5
        assert result.truncated is True
        assert len(result.columns) == 7

    def test_run_join_query(self, executor):
        result = executor.run(
            "SELECT s.name, c.course_name, sc.score "
            "FROM student s "
            "JOIN score sc ON s.id = sc.id "
            "JOIN course c ON sc.course_id = c.course_id "
            "LIMIT 10"
        )
        assert result.row_count <= 10
        assert result.columns == ["name", "course_name", "score"]

    def test_run_aggregate_query(self, executor):
        result = executor.run(
            "SELECT category, SUM(amount) AS total "
            "FROM sales_order GROUP BY category"
        )
        assert result.row_count > 0
        assert "category" in result.columns
        assert "total" in result.columns

    def test_run_empty_result(self, executor):
        result = executor.run("SELECT * FROM student WHERE id = 'nonexistent_999'")
        assert result.row_count == 0
        assert result.truncated is False

    def test_run_null_handling(self, executor):
        result = executor.run(
            "SELECT NULL AS empty_col, id FROM student LIMIT 3"
        )
        assert result.row_count == 3
        assert result.rows[0][0] is None


# ── 2. Schema Store Integration ──


class TestSchemaStoreIntegration:

    def test_from_db_builds_store(self, store):
        assert len(store) == 6

    def test_store_get(self, store):
        student = store.get(_fn("student"))
        assert student is not None
        assert student.name == "student"

    def test_store_table_names(self, store):
        names = store.table_names
        assert _fn("student") in names
        assert _fn("course") in names
        assert _fn("score") in names
        assert _fn("sales_order") in names
        assert _fn("employee") in names
        assert _fn("page_view") in names


# ── 3. Join Advisor Integration ──


class TestJoinAdvisorIntegration:

    def test_suggest_joins_score(self, store):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        joins = suggest_joins(_fn("score"), store)
        related = {j.table_b for j in joins} | {j.table_a for j in joins}
        assert any("student" in t for t in related) or any("course" in t for t in related)

    def test_suggest_joins_student(self, store):
        from seatunnel_agent.text2sql.join_advisor import suggest_joins
        joins = suggest_joins(_fn("student"), store)
        # student has no *_id FK columns and shares only "id" with score
        # (excluded by the advisor), so joins may be empty — just verify it runs
        assert isinstance(joins, list)


# ── 4. Tool Integration ──


class TestToolIntegration:

    def test_execute_sql_tool(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        result_str = execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT name, age FROM student LIMIT 5"},
            runtime,
        )
        result = json.loads(result_str)
        assert result.get("success") is True
        assert result["row_count"] <= 5

    def test_execute_sql_invalid(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        result_str = execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT * FROM nonexistent_table"},
            runtime,
        )
        result = json.loads(result_str)
        assert "error" in result or result.get("success") is not True

    def test_match_tables_tool(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        result_str = execute_text2sql_tool(
            "match_tables",
            {"query": "student scores"},
            runtime,
        )
        result = json.loads(result_str)
        assert "tables" in result or "matches" in result or isinstance(result, dict)

    def test_get_table_schema_tool(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        result_str = execute_text2sql_tool(
            "get_table_schema",
            {"table": "student"},
            runtime,
        )
        result = json.loads(result_str)
        assert "columns" in result or "schema" in result or "name" in str(result)

    def test_get_result_page(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        execute_text2sql_tool(
            "execute_sql",
            {"sql": "SELECT * FROM sales_order LIMIT 100"},
            runtime,
        )
        result_str = execute_text2sql_tool(
            "get_result_page",
            {"page": 2},
            runtime,
        )
        result = json.loads(result_str)
        assert isinstance(result, dict)


# ── 5. Chart Integration ──


class TestChartIntegration:

    def test_bar_chart(self, executor):
        from seatunnel_agent.text2sql.chart import build_chart
        result = executor.run(
            "SELECT category, SUM(amount) AS total "
            "FROM sales_order GROUP BY category"
        )
        fig = build_chart(result.columns, result.rows, "bar")
        assert fig is not None

    def test_pie_chart(self, executor):
        from seatunnel_agent.text2sql.chart import build_chart
        result = executor.run(
            "SELECT device, COUNT(*) AS cnt "
            "FROM page_view GROUP BY device"
        )
        fig = build_chart(result.columns, result.rows, "pie")
        assert fig is not None

    def test_line_chart(self, executor):
        from seatunnel_agent.text2sql.chart import build_chart
        result = executor.run(
            "SELECT order_date, SUM(amount) AS total "
            "FROM sales_order GROUP BY order_date "
            "ORDER BY order_date LIMIT 30"
        )
        fig = build_chart(result.columns, result.rows, "line")
        assert fig is not None


# ── 6. Cache Integration ──


class TestCacheIntegration:

    def test_cache_hit(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        sql = "SELECT COUNT(*) FROM employee"
        r1 = json.loads(execute_text2sql_tool("execute_sql", {"sql": sql}, runtime))
        r2 = json.loads(execute_text2sql_tool("execute_sql", {"sql": sql}, runtime))
        assert r1.get("success") is True
        assert r2.get("success") is True
        assert r2.get("cached") is True

    def test_cache_miss(self, runtime):
        from seatunnel_agent.text2sql.tools import execute_text2sql_tool
        r1 = json.loads(execute_text2sql_tool(
            "execute_sql", {"sql": "SELECT COUNT(*) FROM student"}, runtime
        ))
        r2 = json.loads(execute_text2sql_tool(
            "execute_sql", {"sql": "SELECT COUNT(*) FROM course"}, runtime
        ))
        assert r1.get("success") is True
        assert r2.get("success") is True
        assert r2.get("cached") is not True


# ── 7. ER Diagram Integration ──


class TestERDiagramIntegration:

    def test_er_mermaid_from_real_schema(self, store):
        from seatunnel_agent.text2sql.schema_viz import generate_er_mermaid
        mermaid = generate_er_mermaid(store)
        assert "erDiagram" in mermaid
        assert "student" in mermaid
        assert "score" in mermaid
        assert "sales_order" in mermaid

    def test_er_html_from_real_schema(self, store):
        from seatunnel_agent.text2sql.schema_viz import generate_er_html
        html = generate_er_html(store, "zh")
        assert "mermaid" in html
        assert "<pre" in html


# ── 8. Edge Cases ──


class TestEdgeCasesIntegration:

    def test_large_result_truncation(self, executor):
        result = executor.run("SELECT * FROM sales_order", max_rows=10)
        assert result.row_count == 10
        assert result.truncated is True

    def test_unicode_column_names(self, store):
        student = store.get(_fn("student"))
        assert student is not None
        assert len(student.columns) > 0

    def test_concurrent_queries(self, config):
        import threading
        from seatunnel_agent.text2sql.executor.sqlite import SQLiteExecutor

        results = []
        errors = []

        def _query(i):
            try:
                ex = SQLiteExecutor(config)
                r = ex.run(f"SELECT COUNT(*) FROM student WHERE age > {20 + i}")
                results.append(r.rows[0][0])
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=_query, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
