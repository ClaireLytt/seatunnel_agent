"""Shared SQL/value primitives for the data-comparison package.

Identifier quoting, string casting, the read-only WHERE guard, row-limit
syntax, tunable thresholds and tolerant cross-engine value equality — the
base layer every comparison module builds on (no intra-package imports).
"""

from __future__ import annotations

import math
import os
import re
from typing import Any

try:
    MAX_AGG_COLUMNS = max(1, int(os.getenv("DC_MAX_COMPARE_COLUMNS", "20")))
except ValueError:
    MAX_AGG_COLUMNS = 20

_SAFE_IDENT = re.compile(r"^[\w][\w.$]*$", re.ASCII)

# Tunable limits (previously scattered magic numbers)
try:
    MAX_AGG_COLUMNS = max(1, int(os.getenv("DC_MAX_COMPARE_COLUMNS", "20")))
except ValueError:
    MAX_AGG_COLUMNS = 20
DEFAULT_CHECKSUM_SEGMENTS = 10
STR_CAST_LEN = 200
GINI_SKEW_THRESHOLD = 0.6
# Side-vs-side qualification thresholds: when A and B disagree by more than
# this the skew is a sync-pipeline symptom, not a business fact.
GINI_MISMATCH_THRESHOLD = 0.2
TOP1_MISMATCH_PP = 20.0        # percentage points of top-1 share
TOP1_SKEW_THRESHOLD = 50.0     # top-1 share marking a hot key on one side

# Dialects where backslash is an escape character inside string literals.
_BACKSLASH_ESCAPE_DIALECTS = frozenset(
    {"mysql", "doris", "hive", "sparksql", "clickhouse"})

# ---------------------------------------------------------------------------
# Identifier quoting
# ---------------------------------------------------------------------------

# Engines that quote identifiers with backticks; SQL Server uses brackets;
# everything else gets ANSI double quotes.
_BACKTICK_ENGINES = frozenset({
    "mysql", "doris", "hive", "sparksql", "flinksql", "clickhouse",
})


def quote_identifier(name: str, ds_type: str = "") -> str:
    """Quote a SQL identifier to prevent injection, using the dialect's style.

    Simple names (alphanumeric + underscore/dot/$) pass through unchanged.
    Anything else is quoted with the engine-appropriate delimiter:
    backticks (MySQL family), brackets (SQL Server), or ANSI double quotes.
    """
    if _SAFE_IDENT.match(name):
        return name
    if ds_type in _BACKTICK_ENGINES:
        return "`" + name.replace("`", "``") + "`"
    if ds_type == "sqlserver":
        return "[" + name.replace("]", "]]") + "]"
    return '"' + name.replace('"', '""') + '"'


_STR_CAST_TYPE: dict[str, str] = {
    "hive":     "STRING",
    "sparksql": "STRING",
    "flinksql": "STRING",
    "mysql":    f"CHAR({STR_CAST_LEN})",
    "sqlite":   "TEXT",
}


def cast_to_string(expr: str, ds_type: str = "") -> str:
    """Portable "cast to string" expression for *expr* in the given dialect."""
    if ds_type == "clickhouse":
        return f"toString({expr})"
    return f"CAST({expr} AS {_STR_CAST_TYPE.get(ds_type, f'VARCHAR({STR_CAST_LEN})')})"


_WHERE_WRITE_KEYWORD_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge)\b",
    re.IGNORECASE,
)


def _blank_string_literals(text: str) -> str:
    """Blank the interior of '...' / "..." literals (length-preserving) so
    separators and keywords inside legitimate filter values never trigger
    the checks below."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ("'", '"'):
            i += 1
            while i < n and text[i] != ch:
                if text[i] == "\\":
                    out[i] = " "
                    i += 1
                    if i < n:
                        out[i] = " "
                        i += 1
                    continue
                out[i] = " "
                i += 1
        i += 1
    return "".join(out)


def validate_where(where: str) -> None:
    """Read-only guard for user-supplied WHERE filters (mirrors the text2sql
    validator's strip-literals + keyword-blacklist approach): reject stacked
    statements, comment markers and write/DDL keywords. Raises ValueError."""
    if not where.strip():
        return
    cleaned = _blank_string_literals(where)
    if ";" in cleaned:
        raise ValueError("WHERE 过滤条件不允许包含分号/多语句")
    for marker in ("--", "/*", "#"):
        if marker in cleaned:
            raise ValueError(f"WHERE 过滤条件不允许包含注释符 '{marker}'")
    m = _WHERE_WRITE_KEYWORD_RE.search(cleaned)
    if m:
        raise ValueError(f"WHERE 过滤条件包含写操作关键词 '{m.group(1)}'")


def _where_clause(where: str) -> str:
    validate_where(where)
    return f" WHERE {where}" if where.strip() else ""


def _row_limit(ds_type: str, n: int) -> tuple[str, str]:
    if ds_type == "sqlserver":
        return f"TOP {int(n)} ", ""
    return "", f" LIMIT {int(n)}"


# Cross-source normalization rules for loose value equality. Migrations
# between engines produce "false diffs" from rendering, not data: trailing
# whitespace in CHAR columns, '2024-01-01T00:00:00' vs '2024-01-01 00:00:00'
# vs a bare date, NULL vs '' on engines that conflate them. Each rule can be
# switched via environment variables (documented defaults chosen for the
# common Hive↔MySQL case).
_NORM_TRIM = os.getenv("DC_NORM_TRIM", "1") != "0"
_NORM_TIMESTAMPS = os.getenv("DC_NORM_TIMESTAMPS", "1") != "0"
_NORM_NULL_EQ_EMPTY = os.getenv("DC_NORM_NULL_EQ_EMPTY", "0") == "1"

_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})"                 # date
    r"(?:[T ](\d{2}:\d{2})(?::(\d{2}))?"    # optional time
    r"(?:\.(\d+))?"                         # optional fraction
    r"(Z|[+-]\d{2}:?\d{2})?)?$"             # optional zone suffix
)


def _canon_timestamp(s: str) -> str | None:
    """Canonical 'YYYY-MM-DD HH:MM:SS.frac[zone]' for ISO-ish datetimes.

    A bare date equals midnight; 'T' and ' ' separators, missing seconds and
    trailing fractional zeros are normalized away. The zone suffix is KEPT
    (normalized: 'Z' == '+00:00' == '+0000'), so '10:30:00+08:00' never
    equals '10:30:00Z' — those are instants eight hours apart. Returns None
    when the string is not datetime-shaped."""
    m = _TS_RE.match(s)
    if not m:
        return None
    date, hm, sec, frac, zone = m.groups()
    frac = (frac or "").rstrip("0")
    z = (zone or "").replace(":", "")
    if z in ("+0000", "-0000"):
        z = "Z"
    return (f"{date} {hm or '00:00'}:{sec or '00'}"
            + (f".{frac}" if frac else "") + z)


def _close_enough(a: Any, b: Any, tolerance: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        if _NORM_NULL_EQ_EMPTY and (a in (None, "") and b in (None, "")):
            return True
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        sa, sb = str(a), str(b)
        if _NORM_TRIM:
            sa, sb = sa.strip(), sb.strip()
        if sa == sb:
            return True
        if _NORM_TIMESTAMPS:
            ca, cb = _canon_timestamp(sa), _canon_timestamp(sb)
            if ca is not None and ca == cb:
                return True
        return False
    if math.isnan(fa) and math.isnan(fb):
        return True
    if math.isnan(fa) or math.isnan(fb):
        return False
    if fa == fb:
        return True
    denom = max(abs(fa), abs(fb), 1e-9)
    return abs(fa - fb) / denom < tolerance


