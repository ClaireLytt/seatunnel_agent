# -*- coding: utf-8 -*-
"""Measured consistency check: run the original and the optimized SQL against
the connected datasource and compare the results.

Only a single read-only SELECT/WITH statement is executed (leading SET
statements from an engine-parameter block are skipped, everything else —
multi-statement scripts, writes — makes the script non-comparable). Row
counts are always compared; when the result fits in ``MAX_COMPARE_ROWS``
both result sets are also compared row by row as order-insensitive
multisets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .detector import split_statements
from .i18n import dsk, normalize_lang

MAX_COMPARE_ROWS = 500

_SET_RE = re.compile(r"^\s*set\b", re.IGNORECASE)
_READ_RE = re.compile(r"^\s*(?:select|with)\b", re.IGNORECASE)


def extract_single_select(sql: str) -> str | None:
    """The script's one SELECT/WITH statement, or None when it cannot be
    safely executed for comparison (multi-statement, writes, empty)."""
    stmts = [s.strip().rstrip(";").strip() for _, s in split_statements(sql)]
    stmts = [s for s in stmts if s and not _SET_RE.match(s)]
    if len(stmts) != 1 or not _READ_RE.match(stmts[0]):
        return None
    return stmts[0]


@dataclass
class ConsistencyResult:
    comparable: bool = False
    orig_count: int = -1
    opt_count: int = -1
    rows_compared: bool = False
    rows_match: bool = False
    orig_ms: int = 0
    opt_ms: int = 0
    error: str = ""


def _count(executor, query: str, alias: str) -> tuple[int, int]:
    res = executor.run(f"SELECT COUNT(*) AS c FROM ({query}) {alias}", max_rows=1)
    return int(res.rows[0][0] or 0), res.elapsed_ms


def _row_key(rows) -> list[tuple[str, ...]]:
    return sorted(tuple("" if v is None else str(v) for v in row) for row in rows)


def check_consistency(
    executor,
    original_sql: str,
    optimized_sql: str,
    max_rows: int = MAX_COMPARE_ROWS,
) -> ConsistencyResult:
    r = ConsistencyResult()
    orig = extract_single_select(original_sql)
    opt = extract_single_select(optimized_sql)
    if orig is None or opt is None:
        return r
    r.comparable = True
    try:
        r.orig_count, r.orig_ms = _count(executor, orig, "chk_o")
        r.opt_count, r.opt_ms = _count(executor, opt, "chk_p")
        if r.orig_count == r.opt_count and r.orig_count <= max_rows:
            a = executor.run(orig, max_rows=max_rows)
            b = executor.run(opt, max_rows=max_rows)
            r.orig_ms += a.elapsed_ms
            r.opt_ms += b.elapsed_ms
            r.rows_compared = True
            r.rows_match = _row_key(a.rows) == _row_key(b.rows)
    except Exception as exc:  # noqa: BLE001 — surface in the report section
        r.error = str(exc)
    return r


def render_consistency_section(res: ConsistencyResult, lang: str) -> str:
    """Bilingual '## 一致性实测' markdown section."""
    lang = normalize_lang(lang)
    parts = [dsk(lang, "cst_section"), ""]
    if not res.comparable:
        parts.append(dsk(lang, "cst_not_single"))
        return "\n".join(parts) + "\n"
    if res.error:
        err = res.error.replace("\n", " ")
        parts.append(dsk(lang, "cst_error").format(err=err[:200]))
        return "\n".join(parts) + "\n"
    if res.orig_count != res.opt_count:
        parts.append(dsk(lang, "cst_mismatch").format(a=res.orig_count, b=res.opt_count))
    elif res.rows_compared and res.rows_match:
        parts.append(dsk(lang, "cst_match_full").format(n=res.orig_count))
    elif res.rows_compared:
        parts.append(dsk(lang, "cst_rows_differ"))
    else:
        parts.append(dsk(lang, "cst_match_count"))
    parts += [
        "",
        f"| {dsk(lang, 'cst_col_metric')} | {dsk(lang, 'cst_col_orig')} | {dsk(lang, 'cst_col_opt')} |",
        "|---|---|---|",
        f"| {dsk(lang, 'cst_rows')} | {res.orig_count} | {res.opt_count} |",
        f"| {dsk(lang, 'cst_elapsed')} | {res.orig_ms} ms | {res.opt_ms} ms |",
        "",
    ]
    return "\n".join(parts)
