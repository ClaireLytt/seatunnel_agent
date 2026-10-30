"""Deterministic GRANT/REVOKE surface scanner.

Regex-parses GRANT and REVOKE statements (dialect-tolerant: Hive, Spark,
MySQL, PostgreSQL shapes), nets revokes off, and grades the surviving
grant surface:

* ``public_grant`` (high)        — granted to PUBLIC / '%'
* ``sensitive_grant`` (high)     — grant on a table the PII scanner flags
* ``broad_privilege`` (medium)   — ALL [PRIVILEGES]
* ``wide_scope`` (medium)        — database-level or wildcard scope

Nothing is executed and no catalog is read: sensitivity comes from
running the PII scanner over the same script, so the DDL for flagged
tables has to travel with the grants (same file or directory).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seatunnel_agent.common.severity import severity_counts

KIND_SEVERITY = {
    "public_grant": "high",
    "sensitive_grant": "high",
    "broad_privilege": "medium",
    "wide_scope": "medium",
}

_GRANT_RE = re.compile(
    r"\b(?P<verb>GRANT|REVOKE)\s+(?P<privs>[A-Z_ ,]+?)\s+ON\s+"
    r"(?:(?P<scope>TABLE|DATABASE|SCHEMA)\s+)?(?P<target>[\w.*`\"]+)\s+"
    r"(?:TO|FROM)\s+(?:(?:USER|GROUP|ROLE)\s+)?(?P<principal>[\w%'\"@.]+)",
    re.IGNORECASE)

_PUBLIC = {"public", "'%'", "%", '"public"'}


@dataclass
class GrantStatement:
    verb: str            # grant | revoke
    privileges: list[str]
    scope: str           # table | database
    target: str          # normalized object name (quotes stripped)
    principal: str       # normalized principal (quotes stripped)
    line: int

    def key(self) -> tuple[str, str, str]:
        return (self.target.lower(), self.principal.lower(),
                ",".join(sorted(p.lower() for p in self.privileges)))

    def to_dict(self) -> dict[str, Any]:
        return {"verb": self.verb, "privileges": self.privileges,
                "scope": self.scope, "target": self.target,
                "principal": self.principal, "line": self.line}


@dataclass
class GrantFinding:
    kind: str            # one of KIND_SEVERITY
    severity: str        # high | medium
    target: str
    principal: str
    privileges: list[str]
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "target": self.target, "principal": self.principal,
                "privileges": self.privileges, "detail": self.detail}


@dataclass
class GrantReport:
    root: str
    dialect: str
    grants_seen: int = 0
    revokes_seen: int = 0
    effective: list[GrantStatement] = field(default_factory=list)
    findings: list[GrantFinding] = field(default_factory=list)
    sensitive_tables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "grants_seen": self.grants_seen,
            "revokes_seen": self.revokes_seen,
            "counts": self.counts(),
            "effective": [g.to_dict() for g in self.effective],
            "sensitive_tables": list(self.sensitive_tables),
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


def _norm(token: str) -> str:
    return token.strip().strip("`\"'")


def parse_grants(sql_text: str) -> list[GrantStatement]:
    out: list[GrantStatement] = []
    for m in _GRANT_RE.finditer(sql_text):
        scope = (m.group("scope") or "TABLE").lower()
        out.append(GrantStatement(
            verb=m.group("verb").lower(),
            privileges=[p.strip().upper()
                        for p in m.group("privs").split(",") if p.strip()],
            scope="database" if scope in ("database", "schema") else "table",
            target=_norm(m.group("target")),
            principal=_norm(m.group("principal")),
            line=sql_text.count("\n", 0, m.start()) + 1))
    return out


def _sensitive_tables(sql_text: str, dialect: str) -> set[str]:
    """Tables the PII scanner flags in the same script (lowercased)."""
    from seatunnel_agent.agents.data.pii_scan import scan_sql_text as pii_scan

    try:
        report = pii_scan(sql_text, dialect=dialect)
    except Exception:
        return set()
    return {f.table.lower() for f in report.findings}


def _scan_text(sql_text: str, dialect: str, root: str) -> GrantReport:
    statements = parse_grants(sql_text)
    report = GrantReport(root=root, dialect=dialect)
    report.grants_seen = sum(1 for s in statements if s.verb == "grant")
    report.revokes_seen = sum(1 for s in statements if s.verb == "revoke")

    # net the surface: a later REVOKE with the same (target, principal,
    # privileges) key removes the grant; partial revokes stay conservative
    # (the grant survives) and are left for the human in `effective`
    effective: list[GrantStatement] = []
    for s in statements:
        if s.verb == "grant":
            effective.append(s)
        else:
            effective = [g for g in effective if g.key() != s.key()]
    report.effective = effective

    sensitive = _sensitive_tables(sql_text, dialect)
    report.sensitive_tables = sorted(sensitive)

    def add(kind: str, g: GrantStatement, detail: str) -> None:
        report.findings.append(GrantFinding(
            kind=kind, severity=KIND_SEVERITY[kind], target=g.target,
            principal=g.principal, privileges=g.privileges, detail=detail))

    for g in effective:
        if g.principal.lower() in _PUBLIC:
            add("public_grant", g,
                "granted to PUBLIC - every account inherits it")
        base = g.target.lower().split(".")[-1]
        if g.target.lower() in sensitive or (
                g.scope == "table" and base in
                {t.split(".")[-1] for t in sensitive}):
            add("sensitive_grant", g,
                "table carries PII-flagged columns (see pii_scan)")
        if any(p in ("ALL", "ALL PRIVILEGES") for p in g.privileges):
            add("broad_privilege", g,
                "ALL PRIVILEGES - grant the verbs actually needed")
        if g.scope == "database" or g.target.endswith("*"):
            add("wide_scope", g,
                "database-level / wildcard scope - prefer per-table grants")
    return report


def scan_sql_text(sql_text: str, dialect: str = "hive",
                  root: str = "<inline>") -> GrantReport:
    return _scan_text(sql_text, dialect, root)


def scan_files(paths: list[Path] | list[str], dialect: str = "hive",
               root: str = "") -> GrantReport:
    resolved = [Path(p) for p in paths]
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in resolved)
    return _scan_text(text, dialect, root or str(resolved[0]))


def scan_dir(directory: str | Path, dialect: str = "hive") -> GrantReport:
    base = Path(directory)
    files = sorted(base.rglob("*.sql"))
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in files)
    return _scan_text(text, dialect, str(base))
