"""Deterministic migration guard.

Scans a migration script (the ALTER/DROP/RENAME stream that actually runs
at release time — not two snapshots, which is schema_drift's job), grades
the dangerous operations and generates a best-effort rollback script:

* ``drop_table`` (high)        — undo from a CREATE TABLE in the same
                                 input when present, else irreversible
* ``drop_column`` (high)       — undo with the column type when the CREATE
                                 travels with the script, else irreversible
* ``truncate_table`` (high)    — always irreversible
* ``type_narrowing`` (high)    — new type holds less than the old one
                                 (rank drop, or string family shrinking)
* ``type_change`` (medium)     — type changed, old type unknown or wider
* ``rename_table`` (medium)    — downstream references break; undo reverses
* ``rename_column`` (medium)   — same; undo reverses
* ``not_null_no_default`` (medium) — existing rows reject the constraint

ADD COLUMN is safe (no finding) but still contributes its DROP to the
rollback. The rollback script lists inverses in reverse execution order;
irreversible steps stay in as comments so nothing is silently skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seatunnel_agent.common.severity import severity_counts

KIND_SEVERITY = {
    "drop_table": "high",
    "drop_column": "high",
    "truncate_table": "high",
    "type_narrowing": "high",
    "type_change": "medium",
    "rename_table": "medium",
    "rename_column": "medium",
    "not_null_no_default": "medium",
    # grant_scan cross-check: the object being dropped/renamed still
    # carries net grants someone will chase after the migration
    "live_grants": "medium",
}

_ID = r"[\w.`\"]+"
_RE_DROP_TABLE = re.compile(
    rf"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?P<t>{_ID})", re.I)
_RE_TRUNCATE = re.compile(rf"\bTRUNCATE\s+TABLE\s+(?P<t>{_ID})", re.I)
_RE_DROP_COL = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+DROP\s+COLUMN\s+"
    rf"(?:IF\s+EXISTS\s+)?(?P<c>{_ID})", re.I)
_RE_ADD_COL = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+ADD\s+COLUMNS?\s*\(?\s*"
    rf"(?P<c>{_ID})\s+(?P<type>\w+(?:\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)", re.I)
_RE_RENAME_TABLE = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+RENAME\s+TO\s+(?P<new>{_ID})", re.I)
_RE_RENAME_COL = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+RENAME\s+COLUMN\s+"
    rf"(?P<c>{_ID})\s+TO\s+(?P<new>{_ID})", re.I)
# hive CHANGE covers rename + retype in one statement
_RE_CHANGE_COL = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+CHANGE\s+(?:COLUMN\s+)?"
    rf"(?P<c>{_ID})\s+(?P<new>{_ID})\s+"
    rf"(?P<type>\w+(?:\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)", re.I)
_RE_MODIFY_COL = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<t>{_ID})\s+(?:MODIFY\s+(?:COLUMN\s+)?|"
    rf"ALTER\s+COLUMN\s+)(?P<c>{_ID})\s+(?:TYPE\s+|SET\s+DATA\s+TYPE\s+)?"
    rf"(?P<type>\w+(?:\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)"
    rf"(?P<rest>[^;]*)", re.I)

_INT_RANK = {"tinyint": 1, "smallint": 2, "int": 3, "integer": 3,
             "bigint": 4}
_FLOAT_RANK = {"float": 1, "double": 2}
_STRINGY = ("varchar", "char", "string", "text")


@dataclass
class GuardFinding:
    kind: str            # one of KIND_SEVERITY
    severity: str        # high | medium
    table: str
    column: str = ""
    detail: str = ""
    reversible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "table": self.table, "column": self.column,
                "detail": self.detail, "reversible": self.reversible}


@dataclass
class GuardReport:
    root: str
    dialect: str
    statements_seen: int = 0
    findings: list[GuardFinding] = field(default_factory=list)
    undo_sql: str = ""
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {**severity_counts(self.findings),
                "irreversible": sum(1 for f in self.findings
                                    if not f.reversible)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "statements_seen": self.statements_seen,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
            "undo_sql": self.undo_sql,
            "warnings": list(self.warnings),
        }


def _norm(token: str) -> str:
    return token.strip().strip("`\"")


def _base_type(t: str) -> tuple[str, int | None]:
    """'varchar(64)' -> ('varchar', 64); 'bigint' -> ('bigint', None)."""
    m = re.match(r"(\w+)\s*(?:\(\s*(\d+))?", (t or "").strip().lower())
    if not m:
        return (t or "").strip().lower(), None
    return m.group(1), int(m.group(2)) if m.group(2) else None


def _is_narrowing(old: str, new: str) -> bool:
    ob, on = _base_type(old)
    nb, nn = _base_type(new)
    if ob in _INT_RANK and nb in _INT_RANK:
        return _INT_RANK[nb] < _INT_RANK[ob]
    if ob in _FLOAT_RANK and nb in _FLOAT_RANK:
        return _FLOAT_RANK[nb] < _FLOAT_RANK[ob]
    if ob in _STRINGY and nb in _STRINGY:
        if on is None and nn is not None:
            return True              # unbounded -> bounded
        if on is not None and nn is not None:
            return nn < on
    return False


def _known_types(sql_text: str, dialect: str) -> dict[tuple[str, str], str]:
    """(table, column) -> declared type, from CREATE TABLEs in the input."""
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    try:
        tables, _ = parse_schema_script(sql_text, dialect)
    except Exception:
        return {}
    out: dict[tuple[str, str], str] = {}
    for name, schema in tables.items():
        for col in schema.columns.values():
            out[(name.lower(), col.name.lower())] = col.col_type
            # unqualified lookups too: migration ALTERs often drop the db
            out[(name.lower().split(".")[-1], col.name.lower())] = col.col_type
    return out


def _create_statements(sql_text: str) -> dict[str, str]:
    """table -> its CREATE TABLE statement text, for drop_table undo."""
    out: dict[str, str] = {}
    for stmt in sql_text.split(";"):
        m = re.search(
            rf"\bCREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            rf"(?P<t>{_ID})", stmt, re.I)
        if m:
            out[_norm(m.group("t")).lower()] = stmt.strip() + ";"
    return out


def _scan_text(sql_text: str, dialect: str, root: str) -> GuardReport:
    report = GuardReport(root=root, dialect=dialect)
    report.statements_seen = sum(1 for s in sql_text.split(";") if s.strip())
    types = _known_types(sql_text, dialect)
    creates = _create_statements(sql_text)
    undo: list[str] = []

    def add(kind: str, table: str, column: str = "", detail: str = "",
            reversible: bool = True) -> None:
        report.findings.append(GuardFinding(
            kind=kind, severity=KIND_SEVERITY[kind], table=table,
            column=column, detail=detail, reversible=reversible))

    def col_type(table: str, column: str) -> str:
        return (types.get((table.lower(), column.lower()))
                or types.get((table.lower().split(".")[-1], column.lower()))
                or "")

    # one linear pass keeps undo in execution order; reversed at the end
    events: list[tuple[int, str]] = []       # (position, undo line)

    for m in _RE_DROP_TABLE.finditer(sql_text):
        t = _norm(m.group("t"))
        create = creates.get(t.lower())
        if create:
            add("drop_table", t, detail="CREATE travels with the script - "
                                        "rollback recreates the shell "
                                        "(data is still gone)")
            events.append((m.start(), f"-- data unrecoverable, shell only:\n{create}"))
        else:
            add("drop_table", t, reversible=False,
                detail="no CREATE TABLE in the input - irreversible")
            events.append((m.start(),
                           f"-- IRREVERSIBLE: DROP TABLE {t} (no CREATE in input)"))
    for m in _RE_TRUNCATE.finditer(sql_text):
        t = _norm(m.group("t"))
        add("truncate_table", t, reversible=False,
            detail="TRUNCATE discards every row - irreversible")
        events.append((m.start(), f"-- IRREVERSIBLE: TRUNCATE TABLE {t}"))
    for m in _RE_DROP_COL.finditer(sql_text):
        t, c = _norm(m.group("t")), _norm(m.group("c"))
        ctype = col_type(t, c)
        if ctype:
            add("drop_column", t, c,
                detail=f"type {ctype} known from the input - rollback "
                       "re-adds the column (values are still gone)")
            events.append((m.start(),
                           f"ALTER TABLE {t} ADD COLUMNS ({c} {ctype});"))
        else:
            add("drop_column", t, c, reversible=False,
                detail="column type unknown - irreversible")
            events.append((m.start(),
                           f"-- IRREVERSIBLE: DROP COLUMN {t}.{c} (type unknown)"))
    for m in _RE_ADD_COL.finditer(sql_text):
        t, c = _norm(m.group("t")), _norm(m.group("c"))
        events.append((m.start(), f"ALTER TABLE {t} DROP COLUMN {c};"))
    for m in _RE_RENAME_TABLE.finditer(sql_text):
        t, new = _norm(m.group("t")), _norm(m.group("new"))
        add("rename_table", t, detail=f"renamed to {new} - downstream "
                                      "references break until updated")
        events.append((m.start(), f"ALTER TABLE {new} RENAME TO {t};"))
    for m in _RE_RENAME_COL.finditer(sql_text):
        t, c, new = _norm(m.group("t")), _norm(m.group("c")), _norm(m.group("new"))
        add("rename_column", t, c, detail=f"renamed to {new}")
        events.append((m.start(),
                       f"ALTER TABLE {t} RENAME COLUMN {new} TO {c};"))
    for m in _RE_CHANGE_COL.finditer(sql_text):
        t = _norm(m.group("t"))
        c, new, ntype = _norm(m.group("c")), _norm(m.group("new")), m.group("type")
        old = col_type(t, c)
        if c.lower() != new.lower():
            add("rename_column", t, c, detail=f"renamed to {new}")
        if old and _is_narrowing(old, ntype):
            add("type_narrowing", t, c,
                detail=f"{old} -> {ntype} holds less - values may truncate")
        elif old and _base_type(old) != _base_type(ntype):
            add("type_change", t, c, detail=f"{old} -> {ntype}")
        elif not old:
            add("type_change", t, c,
                detail=f"-> {ntype} (old type unknown)")
        back = old or ntype
        events.append((m.start(),
                       f"ALTER TABLE {t} CHANGE COLUMN {new} {c} {back};"))
    for m in _RE_MODIFY_COL.finditer(sql_text):
        t, c, ntype = _norm(m.group("t")), _norm(m.group("c")), m.group("type")
        old = col_type(t, c)
        if old and _is_narrowing(old, ntype):
            add("type_narrowing", t, c,
                detail=f"{old} -> {ntype} holds less - values may truncate")
        elif old and _base_type(old) != _base_type(ntype):
            add("type_change", t, c, detail=f"{old} -> {ntype}")
        elif not old and _base_type(ntype)[0] not in ("set",):
            add("type_change", t, c,
                detail=f"-> {ntype} (old type unknown)")
        rest = m.group("rest") or ""
        if re.search(r"\bNOT\s+NULL\b", rest, re.I) and not re.search(
                r"\bDEFAULT\b", rest, re.I):
            add("not_null_no_default", t, c,
                detail="NOT NULL added without DEFAULT - existing NULL "
                       "rows reject the constraint")
        if old:
            events.append((m.start(),
                           f"ALTER TABLE {t} MODIFY COLUMN {c} {old};"))
        else:
            events.append((m.start(),
                           f"-- MANUAL: restore previous type of {t}.{c}"))

    # grant_scan cross-check: dropping or renaming a table whose net grants
    # survive leaves principals pointing at nothing (or at the old name)
    from seatunnel_agent.agents.data.grant_scan.scanner import parse_grants

    statements = parse_grants(sql_text)
    effective: list[Any] = []
    for s in statements:
        if s.verb == "grant":
            effective.append(s)
        else:
            effective = [g for g in effective if g.key() != s.key()]
    granted: dict[str, list[str]] = {}
    for g in effective:
        granted.setdefault(g.target.lower(), []).append(g.principal)
    gone = ([(_norm(m.group("t")), "dropped")
             for m in _RE_DROP_TABLE.finditer(sql_text)]
            + [(_norm(m.group("t")), "renamed")
               for m in _RE_RENAME_TABLE.finditer(sql_text)])
    for table, how in gone:
        principals = granted.get(table.lower())
        if principals:
            add("live_grants", table,
                detail=f"{how} while still granted to "
                       f"{', '.join(sorted(set(principals)))} - revoke or "
                       "re-grant as part of the migration")

    undo = [line for _, line in sorted(events, key=lambda e: e[0],
                                       reverse=True)]
    if undo:
        report.undo_sql = "-- rollback (reverse execution order)\n" + \
            "\n".join(undo) + "\n"
    return report


def scan_sql_text(sql_text: str, dialect: str = "hive",
                  root: str = "<inline>") -> GuardReport:
    return _scan_text(sql_text, dialect, root)


def scan_files(paths: list[Path] | list[str], dialect: str = "hive",
               root: str = "") -> GuardReport:
    resolved = [Path(p) for p in paths]
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in resolved)
    return _scan_text(text, dialect, root or str(resolved[0]))


def scan_dir(directory: str | Path, dialect: str = "hive") -> GuardReport:
    base = Path(directory)
    files = sorted(base.rglob("*.sql"))
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in files)
    return _scan_text(text, dialect, str(base))
