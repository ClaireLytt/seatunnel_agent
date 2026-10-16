"""Tests for ClickHouse and SQL Server executors (mocked drivers)."""

from unittest.mock import MagicMock, patch


def _ch_executor():
    from seatunnel_agent.agents.data.text2sql.executor.base import DatabaseConfig
    from seatunnel_agent.agents.data.text2sql.executor.clickhouse import (
        ClickHouseExecutor,
    )

    config = DatabaseConfig(
        ds_type="clickhouse", host="localhost", port=8123, database="testdb"
    )
    return ClickHouseExecutor(config)


def _mss_executor():
    from seatunnel_agent.agents.data.text2sql.executor.base import DatabaseConfig
    from seatunnel_agent.agents.data.text2sql.executor.sqlserver import (
        SqlServerExecutor,
    )

    config = DatabaseConfig(
        ds_type="sqlserver", host="localhost", port=1433, database="testdb"
    )
    return SqlServerExecutor(config)


class TestClickHouseExecutor:
    def test_run_passes_break_overflow_mode(self):
        executor = _ch_executor()
        mock_client = MagicMock()
        mock_client.query.return_value = MagicMock(
            column_names=["a"], result_rows=[(1,)]
        )
        with patch.object(executor, "_connect", return_value=mock_client):
            result = executor.run("SELECT a FROM t", max_rows=10)
        settings = mock_client.query.call_args.kwargs["settings"]
        assert settings["max_result_rows"] == 11
        assert settings["result_overflow_mode"] == "break"
        assert result.columns == ["a"]
        assert result.rows == [(1,)]
        assert result.truncated is False
        mock_client.close.assert_called_once()

    def test_run_truncates_when_over_limit(self):
        executor = _ch_executor()
        mock_client = MagicMock()
        mock_client.query.return_value = MagicMock(
            column_names=["a"], result_rows=[(i,) for i in range(6)]
        )
        with patch.object(executor, "_connect", return_value=mock_client):
            result = executor.run("SELECT a FROM t", max_rows=5)
        assert result.truncated is True
        assert result.row_count == 5
        assert len(result.rows) == 5

    def test_run_closes_client_on_error(self):
        executor = _ch_executor()
        mock_client = MagicMock()
        mock_client.query.side_effect = RuntimeError("boom")
        with patch.object(executor, "_connect", return_value=mock_client):
            try:
                executor.run("SELECT 1")
            except RuntimeError:
                pass
        mock_client.close.assert_called_once()

    def test_show_tables(self):
        executor = _ch_executor()
        mock_client = MagicMock()
        mock_client.query.return_value = MagicMock(result_rows=[("t1",), ("t2",)])
        with patch.object(executor, "_connect", return_value=mock_client):
            assert executor.show_tables() == ["t1", "t2"]
        mock_client.close.assert_called_once()

    def test_describe_table(self):
        executor = _ch_executor()
        mock_client = MagicMock()
        cols = MagicMock(result_rows=[("id", "UInt64", "pk"), ("name", "String", None)])
        comment = MagicMock(result_rows=[("orders table",)])
        mock_client.query.side_effect = [cols, comment]
        with patch.object(executor, "_connect", return_value=mock_client):
            schema = executor.describe_table("orders")
        assert schema.name == "orders"
        assert schema.comment == "orders table"
        assert [c.name for c in schema.columns] == ["id", "name"]
        assert schema.columns[1].comment == ""
        mock_client.close.assert_called_once()

    def test_test_connection_failure(self):
        executor = _ch_executor()
        with patch.object(executor, "_connect", side_effect=RuntimeError("refused")):
            ok, msg = executor.test_connection()
        assert ok is False
        assert "refused" in msg


class TestSqlServerExecutor:
    def _mock_conn(self, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    def test_run_truncates_via_dbapi(self):
        executor = _mss_executor()
        cursor = MagicMock()
        cursor.description = [("a",)]
        cursor.fetchmany.return_value = [(i,) for i in range(6)]
        conn = self._mock_conn(cursor)
        with patch.object(executor, "_connect", return_value=conn):
            result = executor.run("SELECT a FROM t", max_rows=5)
        cursor.fetchmany.assert_called_once_with(6)
        assert result.truncated is True
        assert result.row_count == 5
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_show_tables(self):
        executor = _mss_executor()
        cursor = MagicMock()
        cursor.fetchall.return_value = [("t1",), ("t2",)]
        conn = self._mock_conn(cursor)
        with patch.object(executor, "_connect", return_value=conn):
            assert executor.show_tables() == ["t1", "t2"]
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_describe_table(self):
        executor = _mss_executor()
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            ("id", "int", "pk"),
            ("name", "nvarchar(50)", None),
        ]
        cursor.fetchone.return_value = ("orders table",)
        conn = self._mock_conn(cursor)
        with patch.object(executor, "_connect", return_value=conn):
            schema = executor.describe_table("orders")
        assert schema.name == "orders"
        assert schema.comment == "orders table"
        assert [c.dtype for c in schema.columns] == ["int", "nvarchar(50)"]
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_fetch_all_schemas(self):
        executor = _mss_executor()
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [("t1",)],
            [("id", "int", "")],
        ]
        cursor.fetchone.return_value = ("",)
        conn = self._mock_conn(cursor)
        with patch.object(executor, "_connect", return_value=conn):
            schemas = executor.fetch_all_schemas()
        assert len(schemas) == 1
        assert schemas[0].name == "t1"
        conn.close.assert_called_once()
