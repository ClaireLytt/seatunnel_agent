"""Deterministic duplicate-pipeline detection over pasted SQL.

Two teams building the same daily aggregate from the same sources is
the most expensive kind of warehouse waste — double compute, double
storage, and two numbers that drift apart.  This detector parses every
write statement (sql_diff's statement shapes reused), compares targets
by what they read and what they emit, and reports:

* DP001 high/medium — two targets read the exact same source set; high
  when their output expressions also overlap (same math, two tables),
  medium when only the inputs match;
* DP002 low — one target's sources are a proper subset of another's:
  it may be derivable from the wider pipeline instead of re-reading
  the raw sources;
* DP003 medium — one source table is read directly by ``fanout`` or
  more targets: the shared read deserves a consolidated middle layer.

No scheduler or database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["DupFinding", "DupReport", "detect_dup_pipelines"]

SEVERITY = {"DP001": "high", "DP001_INPUT": "medium", "DP002": "low",
            "DP003": "medium"}

_EXPR_OVERLAP = 0.5   # share of identical output expressions → DP001 high


@dataclass
class DupFinding:
    code: str            # DP001 / DP002 / DP003
    severity: str        # high | medium | low
    tables: list[str]    # the targets (or readers) involved
    detail: str = ""     # shared sources / subset relation / fan-out source
    overlap: float = 0.0  # DP001: identical output-expression share

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "tables": list(self.tables), "detail": self.detail,
                "overlap": round(self.overlap, 4)}


@dataclass
class DupReport:
    dialect: str
    targets_total: int = 0
    sources_total: int = 0
    findings: list[DupFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect,
                "targets_total": self.targets_total,
                "sources_total": self.sources_total,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "warnings": list(self.warnings)}


def _expr_overlap(a: dict[str, str], b: dict[str, str]) -> float:
    """Share of identical output expressions between two targets."""
    ea = {e for e in a.values() if e and e != "*"}
    eb = {e for e in b.values() if e and e != "*"}
    if not ea or not eb:
        return 0.0
    return len(ea & eb) / min(len(ea), len(eb))


def detect_dup_pipelines(sql_text: str, dialect: str = "hive",
                         fanout: int = 3) -> DupReport:
    """Pipeline SQL → duplicate-build findings, graded."""
    from seatunnel_agent.agents.data.sql_diff.differ import statement_shapes

    if fanout < 2:
        raise ValueError("fanout must be at least 2")
    shapes, warnings = statement_shapes(sql_text, dialect)
    targets = {s.target: s for s in shapes
               if not s.target.startswith("<select#")}
    if not targets:
        raise ValueError("no write statements (INSERT/CREATE) to compare")

    report = DupReport(dialect=dialect, targets_total=len(targets),
                       warnings=list(warnings))
    readers: dict[str, list[str]] = {}
    for name, shape in targets.items():
        for src in shape.sources:
            readers.setdefault(src, []).append(name)
    report.sources_total = len(readers)

    names = sorted(targets)
    for i, a in enumerate(names):
        sa = set(targets[a].sources)
        if not sa:
            continue
        for b in names[i + 1:]:
            sb = set(targets[b].sources)
            if not sb:
                continue
            if sa == sb:
                overlap = _expr_overlap(targets[a].columns,
                                        targets[b].columns)
                code = ("DP001" if overlap >= _EXPR_OVERLAP
                        else "DP001_INPUT")
                report.findings.append(DupFinding(
                    code="DP001", severity=SEVERITY[code],
                    tables=[a, b], detail=", ".join(sorted(sa)),
                    overlap=overlap))
            elif sa < sb:
                report.findings.append(DupFinding(
                    code="DP002", severity=SEVERITY["DP002"],
                    tables=[a, b], detail=", ".join(sorted(sa))))
            elif sb < sa:
                report.findings.append(DupFinding(
                    code="DP002", severity=SEVERITY["DP002"],
                    tables=[b, a], detail=", ".join(sorted(sb))))

    for src, who in sorted(readers.items()):
        if len(who) >= fanout:
            report.findings.append(DupFinding(
                code="DP003", severity=SEVERITY["DP003"],
                tables=sorted(who), detail=src))
    order = {"high": 0, "medium": 1, "low": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.code,
                                        f.tables))
    return report
