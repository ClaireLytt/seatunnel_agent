"""Tests for chunked (blocked) large-table comparison."""

import sqlite3

import pytest

from seatunnel_agent.data_comparison.chunked import (
    ChunkedResult,
    build_chunk_map_sql,
    build_chunk_rows_sql,
    build_pk_stats_sql,
    compare_chunked,
)


# ---------------------------------------------------------------------------
# SQL builders
# ---------------------------------------------------------------------------

class TestChunkSqlBuilders:
    def test_mysql_chunk_map(self):
        sql = build_chunk_map_sql("orders", "id", ["amount", "status"],
                                  lo=1, width=100.0, ds_type="mysql")
        assert "CONV(SUBSTRING(LOWER(MD5(" in sql
        assert "GROUP BY" in sql
        assert "FLOOR((id - 1) / 100.0)" in sql
        assert "id IS NOT NULL" in sql

    def test_hive_chunk_map(self):
        sql = build_chunk_map_sql("orders", "id", ["amount"],
                                  lo=0, width=50.0, ds_type="hive")
        assert "AS BIGINT" in sql
        assert "MD5(CONCAT_WS(','," in sql

    def test_postgres_chunk_map(self):
        sql = build_chunk_map_sql("orders", "id", ["amount"],
                                  lo=0, width=50.0, ds_type="postgresql")
        assert "::bit(32)::bigint" in sql

    def test_sqlserver_chunk_map(self):
        sql = build_chunk_map_sql("orders", "id", ["amount"],
                                  lo=0, width=50.0, ds_type="sqlserver")
        assert "HASHBYTES('MD5'" in sql

    def test_no_server_hash_raises(self):
        with pytest.raises(ValueError):
            build_chunk_map_sql("t", "id", ["a"], 0, 1.0, ds_type="sqlite")

    def test_where_is_appended(self):
        sql = build_chunk_map_sql("orders", "id", ["amount"], 0, 10.0,
                                  "mysql", where="dt = '2024-01-01'")
        assert "AND (dt = '2024-01-01')" in sql

    def test_chunk_rows_sql_bounds(self):
        sql = build_chunk_rows_sql("orders", "id", ["amount"], 10, 20, "mysql")
        assert "id >= 10" in sql and "id < 20" in sql
        assert "ORDER BY id" in sql

    def test_pk_stats_sql(self):
        sql = build_pk_stats_sql("orders", "id", "mysql")
        assert "COUNT(id), MIN(id), MAX(id)" in sql


# ---------------------------------------------------------------------------
# End-to-end on SQLite (client-side hash fallback path)
# ---------------------------------------------------------------------------

def _make_pair(rows_a, rows_b):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE ta (id INTEGER, amount REAL, status TEXT)")
    conn.execute("CREATE TABLE tb (id INTEGER, amount REAL, status TEXT)")
    conn.executemany("INSERT INTO ta VALUES (?,?,?)", rows_a)
    conn.executemany("INSERT INTO tb VALUES (?,?,?)", rows_b)

    def run(sql, max_rows):
        return conn.execute(sql).fetchmany(max_rows)
    return run


class TestCompareChunked:
    COLS = ["amount", "status"]

    def _base_rows(self, n=30):
        return [(i, i * 10.0, f"s{i % 3}") for i in range(1, n + 1)]

    def test_identical_tables_match(self):
        rows = self._base_rows()
        run = _make_pair(rows, rows)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite", chunk_rows=7)
        assert isinstance(r, ChunkedResult)
        assert r.match
        assert r.mismatched == []
        assert r.chunk_count > 1          # chunking actually happened
        assert not r.only_a and not r.only_b and not r.changed

    def test_modified_row_located(self):
        rows_a = self._base_rows()
        rows_b = [(i, 999.0 if i == 17 else amt, st)
                  for i, amt, st in self._base_rows()]
        run = _make_pair(rows_a, rows_b)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite", chunk_rows=7)
        assert not r.match
        assert len(r.mismatched) == 1
        assert r.changed == [17]
        assert not r.only_a and not r.only_b

    def test_missing_and_extra_rows_located(self):
        rows_a = self._base_rows()                      # has id=5
        rows_b = ([r for r in self._base_rows() if r[0] != 5]
                  + [(99, 990.0, "s0")])                # extra id=99
        run = _make_pair(rows_a, rows_b)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite", chunk_rows=7)
        assert not r.match
        assert r.only_a == [5]
        assert r.only_b == [99]
        assert r.changed == []

    def test_float_tolerance_not_flagged(self):
        rows_a = [(1, 10.0, "x")]
        rows_b = [(1, 10.0 + 1e-9, "x")]
        run = _make_pair(rows_a, rows_b)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite")
        # chunk hash differs (rendered strings differ) → drill runs,
        # but loose row compare says equal → no changed keys
        assert r.changed == []
        assert not r.only_a and not r.only_b

    def test_non_numeric_pk_raises(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE ta (id TEXT, amount REAL, status TEXT)")
        conn.execute("CREATE TABLE tb (id TEXT, amount REAL, status TEXT)")
        conn.execute("INSERT INTO ta VALUES ('a', 1.0, 'x')")
        conn.execute("INSERT INTO tb VALUES ('a', 1.0, 'x')")

        def run(sql, n):
            return conn.execute(sql).fetchmany(n)
        with pytest.raises(ValueError, match="numeric primary key"):
            compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite")

    def test_empty_tables(self):
        run = _make_pair([], [])
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite")
        assert r.match and "empty" in r.note

    def test_client_fallback_noted(self):
        rows = self._base_rows(5)
        run = _make_pair(rows, rows)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite")
        assert "client-side hashing" in r.note
