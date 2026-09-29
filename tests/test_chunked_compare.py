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
        assert "AS SIGNED" in sql          # MySQL CAST accepts SIGNED, not INT
        assert "id IS NOT NULL" in sql

    def test_hive_chunk_map(self):
        sql = build_chunk_map_sql("orders", "id", ["amount"],
                                  lo=0, width=50.0, ds_type="hive")
        assert "AS BIGINT" in sql
        assert "MD5(CONCAT_WS(CHR(31)," in sql

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

    def test_truncated_drill_does_not_fabricate_keys(self):
        # drill cap smaller than the chunk: keys from a capped fetch would
        # report every unfetched row as missing — must be skipped instead
        rows_a = self._base_rows()
        rows_b = [(i, 999.0 if i == 17 else amt, st)
                  for i, amt, st in self._base_rows()]
        run = _make_pair(rows_a, rows_b)
        r = compare_chunked(run, run, "ta", "tb", "id", self.COLS,
                            "sqlite", "sqlite", chunk_rows=30,
                            drill_row_cap=5)
        assert r.drill_truncated
        assert r.only_a == [] and r.only_b == [] and r.changed == []

    def test_pk_only_table_falls_back_to_pk_hash(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE ta (id INTEGER)")
        conn.execute("CREATE TABLE tb (id INTEGER)")
        conn.executemany("INSERT INTO ta VALUES (?)", [(i,) for i in range(1, 6)])
        conn.executemany("INSERT INTO tb VALUES (?)", [(i,) for i in range(1, 5)])

        def run(sql, n):
            return conn.execute(sql).fetchmany(n)
        r = compare_chunked(run, run, "ta", "tb", "id", [],
                            "sqlite", "sqlite")
        assert not r.match
        assert r.only_a == [5]


class TestChunkedReportRoundTrip:
    def test_report_serialization(self):
        from seatunnel_agent.data_comparison.comparator import CompareReport
        from seatunnel_agent.data_comparison.chunked import (
            ChunkedResult, ChunkMismatch)
        chunked = ChunkedResult(
            table_a="ta", table_b="tb", pk_column="id",
            chunk_count=4, chunk_width=10.0, total_a=30, total_b=29,
            mismatched=[ChunkMismatch(chunk_id=1, pk_lo=10.0, pk_hi=20.0,
                                      count_a=8, count_b=7,
                                      hash_a=123, hash_b=456)],
            only_a=[17], changed=[12])
        report = CompareReport(chunked=chunked, elapsed_ms=100)
        restored = CompareReport.from_dict(report.to_dict())
        assert restored.chunked.pk_column == "id"
        assert restored.chunked.mismatched[0].count_b == 7
        assert restored.chunked.only_a == [17]
        assert not restored.chunked.match

    def test_card_renders_restored_report(self):
        from seatunnel_agent.data_comparison.comparator import CompareReport
        from seatunnel_agent.data_comparison.chunked import ChunkedResult
        from seatunnel_agent.data_comparison_ui import build_chunked_card
        report = CompareReport(chunked=ChunkedResult(
            table_a="ta", table_b="tb", pk_column="id",
            chunk_count=2, total_a=5, total_b=5))
        restored = CompareReport.from_dict(report.to_dict())
        html = build_chunked_card(restored.chunked, "zh")
        assert "分块校验" in html and "全部分块一致" in html


class TestHashCollisionSafety:
    """Separator/NULL handling must not let different rows hash equal."""

    def test_comma_in_values_not_ambiguous(self):
        # ('a,b', 'c') vs ('a', 'b,c') used to concat identically
        from seatunnel_agent.data_comparison.chunked import _client_hash
        assert _client_hash(("a,b", "c")) != _client_hash(("a", "b,c"))

    def test_null_not_empty_string(self):
        from seatunnel_agent.data_comparison.chunked import _client_hash
        assert _client_hash((None, "x")) != _client_hash(("", "x"))

    def test_null_position_matters(self):
        from seatunnel_agent.data_comparison.chunked import _client_hash
        assert _client_hash(("a", None, "b")) != _client_hash(("a", "b", None))

    def test_null_vs_empty_row_flagged_end_to_end(self):
        run = _make_pair([(1, 1.0, None)], [(1, 1.0, "")])
        r = compare_chunked(run, run, "ta", "tb", "id",
                            ["amount", "status"], "sqlite", "sqlite")
        assert r.changed == [1]

    def test_server_sql_uses_sentinels(self):
        sql = build_chunk_map_sql("t", "id", ["a", "b"], 0, 10.0, "mysql")
        assert "COALESCE(" in sql
        # sentinels are built via CHAR()/CHR() at runtime: raw control
        # characters in the SQL text break Hive's XML-serialized job conf
        assert "CONCAT_WS(CHAR(31)" in sql
        assert "CHAR(30)" in sql
        assert chr(31) not in sql and chr(30) not in sql

    def test_hive_sql_has_no_control_characters(self):
        sql = build_chunk_map_sql("t", "id", ["a"], 0, 10.0, "hive")
        assert "CHR(31)" in sql and "CHR(30)" in sql
        assert not any(ord(ch) < 32 and ch not in "\n\t" for ch in sql)


class TestClientFallbackSafety:
    def test_all_rows_sql_ordered(self):
        from seatunnel_agent.data_comparison.chunked import build_all_rows_sql
        sql = build_all_rows_sql("t", "id", ["a"], "sqlite")
        assert "ORDER BY" in sql

    def test_client_cap_hit_is_reported(self, monkeypatch):
        import seatunnel_agent.data_comparison.chunked as ch
        monkeypatch.setattr(ch, "CLIENT_FETCH_CAP", 10)
        rows = [(i, i * 1.0, "s") for i in range(1, 31)]
        run = _make_pair(rows, rows)
        r = compare_chunked(run, run, "ta", "tb", "id",
                            ["amount", "status"], "sqlite", "sqlite",
                            chunk_rows=7)
        assert r.drill_truncated
        assert "capped" in r.note


class TestColumnMapping:
    def test_renamed_column_compared_via_columns_b(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE ta (id INTEGER, amount REAL)")
        conn.execute("CREATE TABLE tb (id INTEGER, total REAL)")
        conn.executemany("INSERT INTO ta VALUES (?,?)",
                         [(i, i * 10.0) for i in range(1, 6)])
        rows_b = [(i, 999.0 if i == 3 else i * 10.0) for i in range(1, 6)]
        conn.executemany("INSERT INTO tb VALUES (?,?)", rows_b)

        def run(sql, n):
            return conn.execute(sql).fetchmany(n)
        r = compare_chunked(run, run, "ta", "tb", "id", ["amount"],
                            "sqlite", "sqlite", columns_b=["total"])
        assert r.changed == [3]
