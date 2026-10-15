"""Chunked (blocked) table comparison for large tables — pt-table-checksum
style.

Phase 1 splits the numeric primary-key range into equal-width chunks and
computes, per side, ONE aggregate query: per-chunk row count plus the sum of
an MD5-prefix hash of every row.  Engines sharing the MD5 hash family
(MySQL/Doris, Hive/SparkSQL, PostgreSQL, SQL Server) produce comparable
sums server-side; other engines (SQLite, ClickHouse, …) fall back to
fetching raw rows and hashing client-side, capped by ``CLIENT_FETCH_CAP``.

Row hashing uses the ASCII unit separator (0x1F) between columns and the
record separator (0x1E) as the NULL sentinel — a plain comma separator
would hash ``('a,b','c')`` and ``('a','b,c')`` identically, and
``CONCAT_WS`` silently drops NULLs, so ``(NULL,'x')`` would collide with
``('','x')``: false "all chunks match" verdicts on genuinely different data.

Phase 2 drills only into mismatched chunks (bounded by ``max_drill_chunks``):
raw rows of both sides are fetched and compared client-side with the same
loose equality used elsewhere (float tolerance), so cross-engine rendering
differences can cost an extra drill but never a wrong verdict.  The output
is row-level: primary keys present only in A, only in B, or changed.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable

from .comparator import (
    _close_enough,
    _where_clause,
    cast_to_string,
    quote_identifier,
)

# rows per chunk that phase 1 aims for
DEFAULT_CHUNK_ROWS = 5000
MAX_CHUNKS = 4096
# phase-2 safety caps
DEFAULT_MAX_DRILL_CHUNKS = 10
DEFAULT_DRILL_ROW_CAP = 20_000
# client-side fallback cap (engines without a server-side hash)
CLIENT_FETCH_CAP = 200_000

# Column separator / NULL sentinel for row hashing (see module docstring).
# Client-side they are the raw control characters; server-side they are
# built at runtime via CHR()/CHAR() — embedding the raw bytes in the SQL
# text breaks Hive, whose MapReduce job conf is XML and rejects control
# characters (com.ctc.wstx WstxParsingException: Illegal character).
_SEP = "\x1f"
_NULL = "\x1e"

_CHR_FUNC: dict[str, str] = {
    "mysql":      "CHAR({n})",
    "doris":      "CHR({n})",
    "hive":       "CHR({n})",
    "sparksql":   "CHR({n})",
    "postgresql": "CHR({n})",
    "sqlserver":  "CHAR({n})",
}

# Per-dialect SUM(first-8-hex-chars-of-MD5 as integer).  All expressions
# parse the prefix big-endian and lower-case, so sums are cross-comparable.
_MD5_PREFIX_SUM: dict[str, str] = {
    "mysql":      "SUM(CAST(CONV(SUBSTRING(LOWER(MD5({row})), 1, 8), 16, 10) AS UNSIGNED))",
    "doris":      "SUM(CAST(CONV(SUBSTRING(LOWER(MD5({row})), 1, 8), 16, 10) AS UNSIGNED))",
    "hive":       "SUM(CAST(CONV(SUBSTRING(LOWER(MD5({row})), 1, 8), 16, 10) AS BIGINT))",
    "sparksql":   "SUM(CAST(CONV(SUBSTRING(LOWER(MD5({row})), 1, 8), 16, 10) AS BIGINT))",
    "postgresql": "SUM(('x' || SUBSTRING(LOWER(MD5({row})), 1, 8))::bit(32)::bigint)",
    "sqlserver":  ("SUM(CAST(CONVERT(BIGINT, CONVERT(VARBINARY(4), "
                   "SUBSTRING(LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', {row}), 2)), 1, 8), 2)) AS BIGINT))"),
}

# CAST target for the chunk-id integer. MySQL's CAST only accepts
# SIGNED/UNSIGNED — `CAST(x AS INT)` is a 1064 syntax error there.
_CHUNK_INT_TYPE: dict[str, str] = {
    "mysql": "SIGNED",
    "doris": "BIGINT",
    "sqlserver": "BIGINT",
    "postgresql": "BIGINT",
}


@dataclass
class ChunkMismatch:
    chunk_id: int
    pk_lo: float
    pk_hi: float
    count_a: int
    count_b: int
    hash_a: int | None = None
    hash_b: int | None = None


@dataclass
class ChunkedResult:
    table_a: str
    table_b: str
    pk_column: str
    chunk_count: int = 0
    chunk_width: float = 0.0
    total_a: int = 0
    total_b: int = 0
    mismatched: list[ChunkMismatch] = field(default_factory=list)
    only_a: list = field(default_factory=list)   # pk values missing on B
    only_b: list = field(default_factory=list)   # pk values missing on A
    changed: list = field(default_factory=list)  # pk values whose row differs
    drill_truncated: bool = False
    note: str = ""

    @property
    def match(self) -> bool:
        return not self.mismatched and self.total_a == self.total_b


# ---------------------------------------------------------------------------
# SQL builders
# ---------------------------------------------------------------------------

def _chunk_expr(pk: str, lo: float, width: float, ds_type: str) -> str:
    int_type = _CHUNK_INT_TYPE.get(ds_type, "INT")
    # width is embedded with a decimal point to force float division in
    # integer-division dialects (MySQL/Hive `/` already yields float; the
    # literal keeps it explicit everywhere).
    return f"CAST(FLOOR(({pk} - {lo!r}) / {float(width)!r}) AS {int_type})"


def _row_expr(columns: list[str], ds_type: str) -> str:
    """NULL-safe, separator-safe concatenation of the row's columns."""
    chr_tpl = _CHR_FUNC.get(ds_type, "CHR({n})")
    sep = chr_tpl.format(n=ord(_SEP))
    null = chr_tpl.format(n=ord(_NULL))
    parts = [
        f"COALESCE({cast_to_string(quote_identifier(c, ds_type), ds_type)}, {null})"
        for c in columns
    ]
    return f"CONCAT_WS({sep}, {', '.join(parts)})"


def build_chunk_map_sql(
    table: str, pk_column: str, columns: list[str],
    lo: float, width: float, ds_type: str, where: str = "",
) -> str:
    """Phase-1 SQL: per-chunk row count + MD5-prefix hash sum."""
    tpl = _MD5_PREFIX_SUM.get(ds_type)
    if tpl is None:
        raise ValueError(f"no server-side hash for ds_type={ds_type!r}")
    qt = quote_identifier(table, ds_type)
    qpk = quote_identifier(pk_column, ds_type)
    chunk = _chunk_expr(qpk, lo, width, ds_type)
    cond = f"{qpk} IS NOT NULL"
    if where.strip():
        cond += f" AND ({where.strip()})"
    return (
        f"SELECT {chunk} AS chunk_id,"
        f"\n  COUNT(*) AS cnt,"
        f"\n  {tpl.format(row=_row_expr(columns, ds_type))} AS h"
        f"\n  FROM {qt}"
        f"\n WHERE {cond}"
        f"\n GROUP BY {chunk}"
    )


def build_chunk_rows_sql(
    table: str, pk_column: str, columns: list[str],
    lo: float, hi: float, ds_type: str, where: str = "",
) -> str:
    """Phase-2 SQL: raw pk + columns of one chunk (client-side compare)."""
    qt = quote_identifier(table, ds_type)
    qpk = quote_identifier(pk_column, ds_type)
    qcols = ", ".join(quote_identifier(c, ds_type) for c in columns)
    cond = f"{qpk} >= {lo!r} AND {qpk} < {hi!r}"
    if where.strip():
        cond += f" AND ({where.strip()})"
    return (
        f"SELECT {qpk}, {qcols}"
        f"\n  FROM {qt}"
        f"\n WHERE {cond}"
        f"\n ORDER BY {qpk}"
    )


def build_pk_stats_sql(table: str, pk_column: str, ds_type: str,
                       where: str = "") -> str:
    qt = quote_identifier(table, ds_type)
    qpk = quote_identifier(pk_column, ds_type)
    return (f"SELECT COUNT({qpk}), MIN({qpk}), MAX({qpk})"
            f"\n  FROM {qt}{_where_clause(where)}")


def build_all_rows_sql(table: str, pk_column: str, columns: list[str],
                       ds_type: str, where: str = "") -> str:
    """Fallback fetch for engines without a server-side hash.

    ORDER BY pk so that, when the fetch hits ``CLIENT_FETCH_CAP``, both
    sides cover the same leading key range instead of two arbitrary
    subsets that would mass-mismatch."""
    qt = quote_identifier(table, ds_type)
    qpk = quote_identifier(pk_column, ds_type)
    qcols = ", ".join(quote_identifier(c, ds_type) for c in columns)
    cond = f"{qpk} IS NOT NULL"
    if where.strip():
        cond += f" AND ({where.strip()})"
    return (f"SELECT {qpk}, {qcols}\n  FROM {qt}\n WHERE {cond}"
            f"\n ORDER BY {qpk}")


# ---------------------------------------------------------------------------
# Client-side hashing (fallback + drill compare)
# ---------------------------------------------------------------------------

def _render(v: Any) -> str:
    """Deterministic string rendering used for client-side hashing.

    Both sides render through THIS function, so engine-specific string
    formats never reach the hash. NULL maps to the same sentinel the
    server-side expression uses, distinct from the empty string."""
    if v is None:
        return _NULL
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _client_hash(row: tuple) -> int:
    src = _SEP.join(_render(v) for v in row).encode("utf-8", "replace")
    return int(hashlib.md5(src).hexdigest()[:8], 16)


def _rows_equal(row_a: tuple, row_b: tuple) -> bool:
    if len(row_a) != len(row_b):
        return False
    return all(_close_enough(a, b) for a, b in zip(row_a, row_b))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

RunFn = Callable[[str, int], list[tuple]]   # (sql, max_rows) -> rows

ChunkMap = dict[int, tuple[int, int]]       # chunk_id -> (count, hash_sum)


def _chunk_map_server(run: RunFn, table: str, pk: str, cols: list[str],
                      lo: float, width: float, ds: str,
                      where: str) -> tuple[ChunkMap, bool]:
    sql = build_chunk_map_sql(table, pk, cols, lo, width, ds, where)
    out: ChunkMap = {}
    for r in run(sql, MAX_CHUNKS + 16):
        if r and r[0] is not None:
            out[int(r[0])] = (int(r[1]), int(r[2] or 0))
    return out, False


def _chunk_map_client(run: RunFn, table: str, pk: str, cols: list[str],
                      lo: float, width: float, ds: str,
                      where: str) -> tuple[ChunkMap, bool]:
    sql = build_all_rows_sql(table, pk, cols, ds, where)
    rows = run(sql, CLIENT_FETCH_CAP)
    capped = len(rows) >= CLIENT_FETCH_CAP
    out: ChunkMap = {}
    for r in rows:
        if not r or r[0] is None:
            continue
        cid = int(math.floor((float(r[0]) - lo) / width))
        cnt, h = out.get(cid, (0, 0))
        out[cid] = (cnt + 1, h + _client_hash(tuple(r[1:])))
    return out, capped


def compare_chunked(
    run_a: RunFn, run_b: RunFn,
    table_a: str, table_b: str,
    pk_column: str, columns: list[str],
    ds_a: str, ds_b: str,
    where: str = "",
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    max_drill_chunks: int = DEFAULT_MAX_DRILL_CHUNKS,
    drill_row_cap: int = DEFAULT_DRILL_ROW_CAP,
    columns_b: list[str] | None = None,
    pk_column_b: str | None = None,
) -> ChunkedResult:
    """Two-phase chunked comparison; see module docstring.

    ``columns_b``/``pk_column_b`` support column mapping: positions must
    align with ``columns``/``pk_column`` (side A names)."""
    pk_b = pk_column_b or pk_column
    if not columns:
        # A table whose only shared column is the PK would render an
        # illegal empty CONCAT_WS(); hashing the PK itself still verifies
        # row existence per chunk. Each side hashes its OWN pk name.
        columns, cols_b = [pk_column], [pk_b]
    else:
        cols_b = columns_b if columns_b else columns
    if len(cols_b) != len(columns):
        raise ValueError("columns_b must align 1:1 with columns")

    result = ChunkedResult(table_a=table_a, table_b=table_b,
                           pk_column=pk_column)

    stats_a = run_a(build_pk_stats_sql(table_a, pk_column, ds_a, where), 1)
    stats_b = run_b(build_pk_stats_sql(table_b, pk_b, ds_b, where), 1)
    cnt_a, min_a, max_a = (stats_a[0] if stats_a else (0, None, None))
    cnt_b, min_b, max_b = (stats_b[0] if stats_b else (0, None, None))
    result.total_a, result.total_b = int(cnt_a or 0), int(cnt_b or 0)
    if result.total_a == 0 and result.total_b == 0:
        result.note = "both sides empty"
        return result

    try:
        lo = min(float(v) for v in (min_a, min_b) if v is not None)
        hi = max(float(v) for v in (max_a, max_b) if v is not None)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"chunked compare requires a numeric primary key; "
            f"{pk_column!r} min/max = {min_a!r}/{max_a!r}") from exc

    n_chunks = max(1, min(MAX_CHUNKS, math.ceil(
        max(result.total_a, result.total_b) / max(1, chunk_rows))))
    width = max((hi - lo + 1) / n_chunks, 1e-9)
    result.chunk_count = n_chunks
    result.chunk_width = width

    server_ok = ds_a in _MD5_PREFIX_SUM and ds_b in _MD5_PREFIX_SUM
    mapper = _chunk_map_server if server_ok else _chunk_map_client
    map_a, capped_a = mapper(run_a, table_a, pk_column, columns,
                             lo, width, ds_a, where)
    map_b, capped_b = mapper(run_b, table_b, pk_b, cols_b,
                             lo, width, ds_b, where)
    if capped_a or capped_b:
        result.drill_truncated = True
        result.note = (f"client fetch capped at {CLIENT_FETCH_CAP} rows/side — "
                       f"only the first rows by {pk_column} were verified")
    elif not server_ok:
        result.note = f"client-side hashing (no server hash for {ds_a!r}/{ds_b!r})"

    for cid in sorted(set(map_a) | set(map_b)):
        ca, ha = map_a.get(cid, (0, None))
        cb, hb = map_b.get(cid, (0, None))
        if ca != cb or ha != hb:
            result.mismatched.append(ChunkMismatch(
                chunk_id=cid, pk_lo=lo + cid * width, pk_hi=lo + (cid + 1) * width,
                count_a=ca, count_b=cb, hash_a=ha, hash_b=hb))

    # Phase 2 — row-level drill-down on mismatched chunks
    drill = result.mismatched[:max_drill_chunks]
    result.drill_truncated = (result.drill_truncated
                              or len(result.mismatched) > len(drill))
    for cm in drill:
        rows_a = run_a(build_chunk_rows_sql(
            table_a, pk_column, columns, cm.pk_lo, cm.pk_hi, ds_a, where),
            drill_row_cap)
        rows_b = run_b(build_chunk_rows_sql(
            table_b, pk_b, cols_b, cm.pk_lo, cm.pk_hi, ds_b, where),
            drill_row_cap)
        if len(rows_a) >= drill_row_cap or len(rows_b) >= drill_row_cap:
            # A capped fetch is incomplete: extracting keys from it would
            # report every unfetched row as missing on the other side.
            result.drill_truncated = True
            continue
        by_a = {r[0]: tuple(r[1:]) for r in rows_a if r and r[0] is not None}
        by_b = {r[0]: tuple(r[1:]) for r in rows_b if r and r[0] is not None}
        keys_a, keys_b = set(by_a), set(by_b)
        result.only_a.extend(sorted(keys_a - keys_b, key=str))
        result.only_b.extend(sorted(keys_b - keys_a, key=str))
        result.changed.extend(
            k for k in sorted(keys_a & keys_b, key=str)
            if not _rows_equal(by_a[k], by_b[k]))
    return result
