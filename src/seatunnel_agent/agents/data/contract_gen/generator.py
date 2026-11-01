"""Deterministic data-contract draft generator.

contract_check gates a DDL snapshot against a YAML contract — but
someone has to write that contract first, and nobody does.  This
generator reads the CREATE TABLE DDL (schema_drift parser, nothing
executed) and drafts the contract from what the tables already promise:
every data column with its type, the partition layout, and the comment
discipline the table actually keeps.  The draft round-trips through
``contract_check.parse_contract`` before it is returned, so the output
is always consumable as-is.

Comment policy per table (coverage counts data columns only): every
already-commented column pins ``comment: true``; when coverage reaches
the threshold the table also sets ``require_comments: true`` so future
columns must arrive commented.  Partition columns are declared alongside
data columns (plus ``partitioned_by``) so the draft round-trips with
zero findings against the same DDL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ContractDraft", "TableDraft", "generate_contract"]


@dataclass
class TableDraft:
    name: str
    columns: list[dict[str, Any]] = field(default_factory=list)
    partitioned_by: list[str] = field(default_factory=list)
    require_comments: bool = False
    allow_extra_columns: bool = True
    comment_coverage: float = 1.0   # commented / data columns

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "columns": list(self.columns),
                "partitioned_by": list(self.partitioned_by),
                "require_comments": self.require_comments,
                "allow_extra_columns": self.allow_extra_columns,
                "comment_coverage": round(self.comment_coverage, 4)}


@dataclass
class ContractDraft:
    dialect: str
    tables: list[TableDraft] = field(default_factory=list)
    yaml_text: str = ""
    columns_total: int = 0
    comment_coverage: float = 1.0   # overall, data columns only
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect,
                "tables_total": len(self.tables),
                "columns_total": self.columns_total,
                "comment_coverage": round(self.comment_coverage, 4),
                "tables": [t.to_dict() for t in self.tables],
                "yaml_text": self.yaml_text,
                "warnings": list(self.warnings)}


def _quote(value: str) -> str:
    """YAML-safe scalar: quote when anything could surprise the loader."""
    import re

    if re.fullmatch(r"[A-Za-z0-9_.\-]+", value or ""):
        return value
    return '"' + (value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_yaml(tables: list[TableDraft], with_types: bool) -> str:
    lines: list[str] = ["tables:"]
    for t in tables:
        lines.append(f"  - name: {_quote(t.name)}")
        if t.columns:
            lines.append("    columns:")
            for c in t.columns:
                lines.append(f"      - name: {_quote(str(c['name']))}")
                if with_types and c.get("type"):
                    lines.append(f"        type: {_quote(str(c['type']))}")
                if c.get("comment"):
                    lines.append("        comment: true")
        if t.require_comments:
            lines.append("    require_comments: true")
        if t.partitioned_by:
            rendered = ", ".join(_quote(p) for p in t.partitioned_by)
            lines.append(f"    partitioned_by: [{rendered}]")
        if not t.allow_extra_columns:
            lines.append("    allow_extra_columns: false")
    return "\n".join(lines) + "\n"


def generate_contract(sql_text: str, dialect: str = "hive",
                      with_types: bool = True,
                      comment_threshold: float = 0.8,
                      allow_extra: bool = True,
                      tables: list[str] | None = None) -> ContractDraft:
    """CREATE TABLE DDL -> contract_check-consumable YAML draft.

    *tables*, when given, restricts the draft to those names
    (case-insensitive).  Raises ValueError when the DDL yields no
    tables or a requested table is absent.
    """
    from seatunnel_agent.agents.data.contract_check.checker import (
        parse_contract,
    )
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    if not (sql_text or "").strip():
        raise ValueError("DDL must not be empty")
    if not 0.0 <= comment_threshold <= 1.0:
        raise ValueError("comment_threshold must be within [0, 1]")
    parsed, warnings = parse_schema_script(sql_text, dialect)
    if not parsed:
        raise ValueError("no CREATE TABLE found in the DDL"
                         + (f" ({warnings[0]})" if warnings else ""))
    if tables:
        want = {t.strip().lower() for t in tables if t.strip()}
        missing = want - {n.lower() for n in parsed}
        if missing:
            raise ValueError("table(s) not in the DDL: "
                             + ", ".join(sorted(missing)))
        parsed = {n: s for n, s in parsed.items() if n.lower() in want}

    drafts: list[TableDraft] = []
    total_cols = 0
    total_commented = 0
    for name in sorted(parsed):
        schema = parsed[name]
        data_cols = [c for c in schema.columns.values()
                     if not c.is_partition]
        commented = sum(1 for c in data_cols if (c.comment or "").strip())
        coverage = commented / len(data_cols) if data_cols else 1.0
        hold_line = bool(data_cols) and coverage >= comment_threshold
        cols: list[dict[str, Any]] = []
        for c in schema.columns.values():   # partitions declared too, so
            entry: dict[str, Any] = {"name": c.name}  # require_comments
            if with_types and c.col_type:             # round-trips clean
                entry["type"] = c.col_type.lower()
            if (c.comment or "").strip():
                entry["comment"] = True
            cols.append(entry)
        drafts.append(TableDraft(
            name=name, columns=cols,
            partitioned_by=list(schema.partition_cols),
            require_comments=hold_line,
            allow_extra_columns=allow_extra,
            comment_coverage=coverage))
        total_cols += len(data_cols)
        total_commented += commented

    yaml_text = _render_yaml(drafts, with_types)
    parse_contract(yaml_text)   # round-trip guard: draft must be consumable
    return ContractDraft(
        dialect=dialect, tables=drafts, yaml_text=yaml_text,
        columns_total=total_cols,
        comment_coverage=(total_commented / total_cols
                          if total_cols else 1.0),
        warnings=list(warnings))
