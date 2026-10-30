"""Masking-SQL generator — the disposal half of the PII scanner.

``scanner`` answers *where the sensitive columns are*; this module answers
*what to run about it*: for every table whose DDL we parsed it emits a
``CREATE OR REPLACE VIEW <table>_masked AS SELECT ...`` with each flagged
column replaced by a category-appropriate masking expression, every other
column passed through untouched. Columns known only from lineage (no DDL,
so the full column list is unknown) degrade to expression snippets plus a
warning instead of a view.

Deterministic: no LLM, nothing executed. Expressions stick to functions
shared by hive/spark (concat/substr/instr/regexp_replace/md5/cast) so the
output runs on the dialects the suite already targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .rules import DEFAULT_RULES, PiiRule
from .scanner import (
    ColumnRef,
    PiiFinding,
    PiiReport,
    collect_columns_from_ddl,
    scan_dir,
    scan_files,
    scan_sql_text,
)

# category -> expression template. {c} is the column reference; numeric or
# otherwise unmaskable-by-truncation categories fall back to suppression.
MASK_TEMPLATES: dict[str, str] = {
    "phone":         "concat(substr({c}, 1, 3), '****', substr({c}, -4))",
    "id_card":       "concat(substr({c}, 1, 6), '********', substr({c}, -4))",
    "bank_card":     "concat('************', substr({c}, -4))",
    "passport":      "concat(substr({c}, 1, 1), '********')",
    "email":         "concat(substr({c}, 1, 1), '***', substr({c}, instr({c}, '@')))",
    "person_name":   "concat(substr({c}, 1, 1), '**')",
    "address":       "concat(substr({c}, 1, 6), '****')",
    "salary":        "cast(null as {t})",
    "birthday":      "concat(substr(cast({c} as string), 1, 4), '-**-**')",
    "license_plate": "concat(substr({c}, 1, 2), '***', substr({c}, -2))",
    "ip_address":    "regexp_replace(cast({c} as string), '\\\\.[0-9]+\\\\.[0-9]+$', '.*.*')",
}

# custom-rule categories and anything unknown: one-way hash keeps joins alive
FALLBACK_TEMPLATE = "md5(cast({c} as string))"

_NUMERIC_TYPES = ("int", "bigint", "double", "float", "decimal", "numeric")


def mask_expression(category: str, column: str, col_type: str = "") -> str:
    template = MASK_TEMPLATES.get(category, FALLBACK_TEMPLATE)
    t = (col_type or "").strip().lower() or "string"
    # cast(null as <t>) needs a concrete type; unparametrised decimal is fine
    if "{t}" in template and not any(t.startswith(n) for n in _NUMERIC_TYPES):
        t = "string" if not t or t == "string" else t
    return template.format(c=column, t=t or "string")


@dataclass
class MaskColumn:
    table: str
    column: str
    category: str
    severity: str
    confidence: str
    expression: str

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "column": self.column,
                "category": self.category, "severity": self.severity,
                "confidence": self.confidence, "expression": self.expression}


@dataclass
class TableMaskPlan:
    table: str
    view_name: str
    columns: list[str]                       # full DDL order
    masked: list[MaskColumn]
    view_sql: str

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "view_name": self.view_name,
                "columns": list(self.columns),
                "masked": [m.to_dict() for m in self.masked],
                "view_sql": self.view_sql}


@dataclass
class Uncovered:
    table: str
    column: str
    category: str
    severity: str
    reason: str          # "no_ddl" | "below_min_confidence"
    unmasked_spread: int

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "column": self.column,
                "category": self.category, "severity": self.severity,
                "reason": self.reason,
                "unmasked_spread": self.unmasked_spread}


@dataclass
class Coverage:
    """Verification half: assuming consumers switch to the generated views,
    which scan findings are remediated and which unmasked spread remains."""

    findings_total: int = 0
    covered: int = 0
    uncovered: list[Uncovered] = field(default_factory=list)
    unmasked_edges_before: int = 0
    unmasked_edges_after: int = 0

    def worst_uncovered(self) -> str | None:
        rank = {"low": 1, "medium": 2, "high": 3}
        if not self.uncovered:
            return None
        return max(self.uncovered, key=lambda u: rank[u.severity]).severity

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings_total": self.findings_total,
            "covered": self.covered,
            "uncovered": [u.to_dict() for u in self.uncovered],
            "unmasked_edges_before": self.unmasked_edges_before,
            "unmasked_edges_after": self.unmasked_edges_after,
        }


@dataclass
class MaskPlan:
    root: str
    dialect: str
    tables: list[TableMaskPlan] = field(default_factory=list)
    expressions_only: list[MaskColumn] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)  # below min_confidence
    warnings: list[str] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)

    def counts(self) -> dict[str, int]:
        return {
            "views": len(self.tables),
            "masked_columns": sum(len(t.masked) for t in self.tables)
            + len(self.expressions_only),
            "expressions_only": len(self.expressions_only),
            "skipped": len(self.skipped),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "counts": self.counts(),
            "tables": [t.to_dict() for t in self.tables],
            "expressions_only": [m.to_dict() for m in self.expressions_only],
            "skipped": list(self.skipped),
            "warnings": list(self.warnings),
            "coverage": self.coverage.to_dict(),
        }


_CONF_RANK = {"low": 1, "high": 2}


def build_mask_plan(report: PiiReport, inventory: list[ColumnRef],
                    min_confidence: str = "low") -> MaskPlan:
    """Join scan findings with the DDL column inventory into view DDL."""
    plan = MaskPlan(root=report.root, dialect=report.dialect,
                    warnings=list(report.warnings))
    threshold = _CONF_RANK.get(min_confidence, 1)

    ddl_tables: dict[str, list[ColumnRef]] = {}
    for ref in inventory:
        if ref.origin == "ddl":
            ddl_tables.setdefault(ref.table, []).append(ref)
    types = {(r.table, r.column): r.col_type for r in inventory}

    cov = plan.coverage
    cov.findings_total = len(report.findings)
    cov.unmasked_edges_before = sum(
        len(f.unmasked_edges) for f in report.findings)

    findings: dict[str, list[PiiFinding]] = {}
    for f in report.findings:
        if _CONF_RANK.get(f.confidence, 1) < threshold:
            plan.skipped.append({"table": f.table, "column": f.column,
                                 "category": f.category,
                                 "confidence": f.confidence})
            cov.uncovered.append(Uncovered(
                table=f.table, column=f.column, category=f.category,
                severity=f.severity, reason="below_min_confidence",
                unmasked_spread=len(f.unmasked_edges)))
            continue
        findings.setdefault(f.table, []).append(f)

    for table in sorted(findings):
        masked = [
            MaskColumn(
                table=table, column=f.column, category=f.category,
                severity=f.severity, confidence=f.confidence,
                expression=mask_expression(
                    f.category, f.column, types.get((table, f.column), "")),
            )
            for f in sorted(findings[table], key=lambda f: f.column)
        ]
        refs = ddl_tables.get(table)
        if not refs:
            plan.expressions_only.extend(masked)
            plan.warnings.append(
                f"{table}: 仅来自血缘、无 DDL，无法生成完整视图，只给出列表达式")
            for f in findings[table]:
                cov.uncovered.append(Uncovered(
                    table=f.table, column=f.column, category=f.category,
                    severity=f.severity, reason="no_ddl",
                    unmasked_spread=len(f.unmasked_edges)))
            continue
        cov.covered += len(findings[table])
        by_col = {m.column: m for m in masked}
        lines: list[str] = []
        for ref in refs:  # DDL order is preserved by parse_schema_script
            m = by_col.get(ref.column)
            if m is None:
                lines.append(f"  {ref.column}")
            else:
                lines.append(
                    f"  {m.expression} AS {ref.column}"
                    f"  -- {m.category} · {m.severity}")
        view_name = f"{table}_masked"
        view_sql = (
            f"CREATE OR REPLACE VIEW {view_name} AS\nSELECT\n"
            + ",\n".join(lines)
            + f"\nFROM {table};"
        )
        plan.tables.append(TableMaskPlan(
            table=table, view_name=view_name,
            columns=[r.column for r in refs],
            masked=masked, view_sql=view_sql))

    cov.unmasked_edges_after = sum(u.unmasked_spread for u in cov.uncovered)
    return plan


def render_mask_sql(plan: MaskPlan) -> str:
    """One executable SQL script: every view, then expression-only snippets."""
    parts: list[str] = [
        "-- Generated by seatunnel-agent pii --mask (deterministic).",
        f"-- root: {plan.root} · dialect: {plan.dialect}",
        "-- Review before running: masking widths assume typical CN formats.",
        "",
    ]
    for t in plan.tables:
        parts.append(f"-- {t.table}: {len(t.masked)}/{len(t.columns)} 列脱敏")
        parts.append(t.view_sql)
        parts.append("")
    if plan.expressions_only:
        parts.append("-- 以下列只有血缘、没有 DDL，无法生成完整视图，"
                     "请把表达式带回你的 ETL：")
        for m in plan.expressions_only:
            parts.append(f"--   {m.table}.{m.column} ({m.category}) -> "
                         f"{m.expression}")
        parts.append("")
    cov = plan.coverage
    parts.append("-- 覆盖回验 coverage: "
                 f"{cov.covered}/{cov.findings_total} findings covered; "
                 f"unmasked spread edges {cov.unmasked_edges_before} -> "
                 f"{cov.unmasked_edges_after}")
    for u in cov.uncovered:
        parts.append(f"--   UNCOVERED {u.table}.{u.column} "
                     f"({u.category} · {u.severity}) reason={u.reason}")
    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# convenience entry points mirroring scanner.scan_*
# ---------------------------------------------------------------------------

def plan_sql_text(sql_text: str, dialect: str = "hive",
                  rules: list[PiiRule] | None = None,
                  min_confidence: str = "low") -> MaskPlan:
    report = scan_sql_text(sql_text, dialect=dialect,
                           rules=rules or list(DEFAULT_RULES))
    inventory, _ = collect_columns_from_ddl(sql_text, dialect)
    return build_mask_plan(report, inventory, min_confidence)


def plan_files(paths: list[Path], dialect: str = "hive",
               rules: list[PiiRule] | None = None,
               min_confidence: str = "low", root: str = "") -> MaskPlan:
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in paths)
    report = scan_files(paths, dialect=dialect,
                        rules=rules or list(DEFAULT_RULES),
                        root=root or str(paths[0]))
    inventory, _ = collect_columns_from_ddl(text, dialect)
    return build_mask_plan(report, inventory, min_confidence)


def plan_dir(directory: str | Path, dialect: str = "hive",
             rules: list[PiiRule] | None = None,
             min_confidence: str = "low") -> MaskPlan:
    base = Path(directory)
    paths = sorted(base.rglob("*.sql"))
    report = scan_dir(base, dialect=dialect,
                      rules=rules or list(DEFAULT_RULES))
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in paths)
    inventory, _ = collect_columns_from_ddl(text, dialect)
    return build_mask_plan(report, inventory, min_confidence)
