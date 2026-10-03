# -*- coding: utf-8 -*-
"""Deterministic SQL formatting core (sqlglot pretty-print).

Statements are split and formatted one by one: a statement that fails to
parse is kept VERBATIM (never mangled) and reported as a parse error, so a
``--write`` run can never destroy content. ``changed`` compares
whitespace-normalized text, so an already-formatted file stays untouched.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FmtResult:
    name: str
    original: str
    formatted: str
    statements: int = 0
    failed: int = 0                      # parse failures kept verbatim
    parse_errors: list[str] = field(default_factory=list)
    select_star: int = 0                 # style finding: bare SELECT *

    @property
    def changed(self) -> bool:
        return self.original.strip() != self.formatted.strip()

    def diff(self) -> str:
        if not self.changed:
            return ""
        return "".join(difflib.unified_diff(
            self.original.strip().splitlines(keepends=True),
            self.formatted.strip().splitlines(keepends=True),
            fromfile=f"{self.name} (original)",
            tofile=f"{self.name} (formatted)",
            lineterm="\n"))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "changed": self.changed,
                "statements": self.statements, "failed": self.failed,
                "parse_errors": list(self.parse_errors),
                "select_star": self.select_star,
                "formatted": self.formatted, "diff": self.diff()}


@dataclass
class FmtFileResult:
    path: str
    result: FmtResult
    written: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = self.result.to_dict()
        data["path"] = self.path
        data["written"] = self.written
        data.pop("formatted", None)      # batch payloads skip full bodies
        return data


def format_text(sql: str, dialect: str = "hive",
                name: str = "<inline>") -> FmtResult:
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

    read = resolve_sqlglot_dialect(dialect)
    result = FmtResult(name=name, original=sql, formatted=sql)
    try:
        statements = sqlglot.parse(sql, read=read)
    except sqlglot.errors.ParseError as exc:
        # whole-script failure: untouched, one error
        result.statements = 1
        result.failed = 1
        result.parse_errors.append(_clean_error(exc))
        return result

    pieces: list[str] = []
    for tree in statements:
        if tree is None:
            continue
        result.statements += 1
        try:
            pieces.append(tree.sql(dialect=read, pretty=True))
            for select in tree.find_all(exp.Select):
                if any(isinstance(e, exp.Star) for e in select.expressions):
                    result.select_star += 1
        except Exception as exc:  # noqa: BLE001 — keep the statement verbatim
            result.failed += 1
            result.parse_errors.append(_clean_error(exc))
            pieces.append("-- sqlfmt: kept verbatim (render failed)\n"
                          + sql.strip())
    result.formatted = ";\n\n".join(pieces) + (";\n" if pieces else "")
    return result


def _clean_error(exc: Exception) -> str:
    return " ".join(str(exc).split())[:200]


def collect_sql_files(directory: str | Path) -> list[Path]:
    return sorted(p for p in Path(directory).rglob("*.sql") if p.is_file())


def fmt_dir(directory: str | Path, dialect: str = "hive",
            write: bool = False) -> list[FmtFileResult]:
    out: list[FmtFileResult] = []
    for path in collect_sql_files(directory):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result = FmtResult(name=str(path), original="", formatted="")
            result.statements = result.failed = 1
            result.parse_errors.append(f"无法读取: {exc}")
            out.append(FmtFileResult(path=str(path), result=result))
            continue
        result = format_text(text, dialect=dialect, name=str(path))
        written = False
        # never write a file whose statements could not all be formatted
        if write and result.changed and not result.failed:
            path.write_text(result.formatted, encoding="utf-8")
            written = True
        out.append(FmtFileResult(path=str(path), result=result,
                                 written=written))
    return out
