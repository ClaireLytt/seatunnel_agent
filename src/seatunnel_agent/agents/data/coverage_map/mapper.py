"""Deterministic quality-coverage map: which tables are protected.

dq_rulegen writes rule files and contract_gen writes contracts — but
nobody can say which tables actually have either.  Paste the warehouse
DDL (schema_drift parser reused), the DQC rules YAML (data_quality's
parser reused) and optionally the contract YAML (contract_check's
parser reused), and every table gets its protection row:

* which DQC check types gate it (row_count / null_rate / unique /
  enum_domain) and whether a contract declares it;
* CM001 — a table with no protection at all: medium, high when it
  lives in a fact/serving layer (dwd / dws / ads) where consumers
  feel the breakage;
* CM002 medium — a rule or contract naming a table absent from the
  DDL: a dead gate guarding nothing;
* overall coverage share, uncovered tables first.

No database connection — the map reads the same artifacts the gates do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["CoverageMap", "CoverageFinding", "TableCoverage",
           "map_coverage"]

_HOT_LAYERS = ("dwd", "dws", "ads")
_CHECK_TYPES = ("row_count", "null_rate", "unique", "enum_domain")


@dataclass
class TableCoverage:
    table: str
    checks: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(_CHECK_TYPES, 0))
    contract: bool = False

    @property
    def covered(self) -> bool:
        return self.contract or any(self.checks.values())

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "checks": dict(self.checks),
                "contract": self.contract, "covered": self.covered}


@dataclass
class CoverageFinding:
    code: str            # CM001 | CM002
    severity: str        # high | medium
    table: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "detail": self.detail}


@dataclass
class CoverageMap:
    tables: list[TableCoverage] = field(default_factory=list)
    findings: list[CoverageFinding] = field(default_factory=list)
    covered: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def coverage_share(self) -> float:
        return self.covered / len(self.tables) if self.tables else 0.0

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"tables_total": len(self.tables),
                "covered": self.covered,
                "coverage_share": round(self.coverage_share, 4),
                "counts": self.counts(),
                "tables": [t.to_dict() for t in self.tables],
                "findings": [f.to_dict() for f in self.findings],
                "warnings": list(self.warnings)}


def _layer(table: str) -> str:
    import re

    return re.split(r"[._]", table, maxsplit=1)[0].lower()


def map_coverage(ddl_text: str, rules_text: str = "",
                 contract_text: str = "",
                 dialect: str = "hive") -> CoverageMap:
    """DDL + gate artifacts → per-table protection map."""
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    schemas, warnings = parse_schema_script(ddl_text, dialect)
    if not schemas:
        raise ValueError("no CREATE TABLE found in the DDL"
                         + (f" ({warnings[0]})" if warnings else ""))
    if not (rules_text or "").strip() and not (contract_text or "").strip():
        raise ValueError("paste the DQC rules YAML, the contract YAML, "
                         "or both — the map needs at least one gate "
                         "artifact")

    cmap = CoverageMap(warnings=list(warnings))
    by_lower = {name.lower(): TableCoverage(table=name)
                for name in sorted(schemas)}
    dead: list[tuple[str, str]] = []     # (artifact, table)

    if (rules_text or "").strip():
        from seatunnel_agent.agents.data.data_quality.rules import (
            parse_rules_text,
        )

        rules, errors = parse_rules_text(rules_text)
        if errors:
            raise ValueError(f"rules YAML: {errors[0]}")
        for rule in rules:
            tc = by_lower.get(rule.table.lower())
            if tc is None:
                dead.append(("dqc", rule.table))
                continue
            for check in rule.checks:
                if check.type in tc.checks:
                    tc.checks[check.type] += 1

    if (contract_text or "").strip():
        from seatunnel_agent.agents.data.contract_check.checker import (
            parse_contract,
        )

        for contract in parse_contract(contract_text):
            tc = by_lower.get(contract.name.lower())
            if tc is None:
                dead.append(("contract", contract.name))
                continue
            tc.contract = True

    for tc in by_lower.values():
        cmap.tables.append(tc)
        if tc.covered:
            cmap.covered += 1
        else:
            hot = _layer(tc.table) in _HOT_LAYERS
            cmap.findings.append(CoverageFinding(
                "CM001", "high" if hot else "medium", tc.table))
    for artifact, table in sorted(set(dead)):
        cmap.findings.append(CoverageFinding(
            "CM002", "medium", table, artifact))

    cmap.tables.sort(key=lambda t: (t.covered, t.table))
    order = {"high": 0, "medium": 1}
    cmap.findings.sort(key=lambda f: (order[f.severity], f.code, f.table))
    return cmap
