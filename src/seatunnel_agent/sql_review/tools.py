"""Tool definitions and execution for the SQL Review agent.

The runtime carries the SQL under review, the schema store (optional) and
the accumulated findings across tool calls in one review session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..text2sql.schema import SchemaStore
from .config import ReviewConfig
from .lineage import extract_table_lineage
from .linter import lint_sql, normalize_dialect
from .report import CHECK_CATALOG, Finding, ReviewReport, Severity, render_report

if TYPE_CHECKING:
    from ..data_lineage.graph import LineageGraph

_IMPACT_MAX_TABLES = 50

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "lint_sql",
        "description": (
            "Run deterministic static lint rules on the SQL under review "
            "(GROUP BY completeness, cartesian joins, NULL comparison, "
            "partition filters, division-by-zero, SELECT *, etc.). Returns "
            "findings with exact line numbers. Always call this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_table_schema",
        "description": (
            "Get the schema of a referenced table: columns with types and "
            "comments, partition columns. Only available when the review "
            "session was given a database connection or DDL. Use it to "
            "verify JOIN key types, column existence and partition keys."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Full table name, e.g. zz.dwm_scm_detail_di",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "lineage_impact",
        "description": (
            "Query the data-lineage graph for downstream tables affected by "
            "this SQL's write targets (INSERT/CTAS). Returns affected tables "
            "with layer and SLA markers so you can judge the blast radius and "
            "mention it in finding impact. Use it when the SQL writes to a "
            "table. If no lineage directories are configured the tool "
            "returns a hint instead of failing — just skip impact analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "覆盖默认目标表；缺省时自动取 SQL 的写入目标表",
                },
                "depth": {
                    "type": "integer",
                    "description": "下游追溯层数，默认 3",
                },
            },
        },
    },
    {
        "name": "submit_review",
        "description": (
            "Submit the final review. Provide the findings YOU discovered "
            "(linter findings are merged automatically — do not repeat them) "
            "and an overall verdict. Returns the rendered CR report, which "
            "you must output verbatim as your final answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "Findings from your semantic review",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["critical", "risk", "suggestion"],
                            },
                            "category": {
                                "type": "string",
                                "description": "One of the 15 checklist keys",
                            },
                            "description": {"type": "string", "description": "问题描述"},
                            "location": {"type": "string", "description": "代码位置, e.g. 行 6"},
                            "impact": {"type": "string", "description": "影响范围/风险说明"},
                            "suggestion": {"type": "string", "description": "修复/优化建议"},
                        },
                        "required": ["severity", "category", "description", "location"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "总体评价, one or two sentences in Chinese",
                },
            },
            "required": ["findings", "summary"],
        },
    },
]


@dataclass
class SQLReviewRuntime:
    sql: str
    dialect: str = "hive"
    store: SchemaStore | None = None
    config: ReviewConfig | None = None
    lineage_graph: "LineageGraph | None" = None
    lint_findings: list[Finding] = field(default_factory=list)
    last_report: str = ""
    report: ReviewReport | None = None

    def __post_init__(self) -> None:
        self.dialect = normalize_dialect(self.dialect)


def _tool_lint_sql(inp: dict[str, Any], rt: SQLReviewRuntime) -> dict[str, Any]:
    rt.lint_findings = lint_sql(rt.sql, rt.dialect, store=rt.store, config=rt.config)
    return {
        "success": True,
        "finding_count": len(rt.lint_findings),
        "findings": [f.to_dict() for f in rt.lint_findings],
    }


def _tool_get_table_schema(inp: dict[str, Any], rt: SQLReviewRuntime) -> dict[str, Any]:
    if rt.store is None or len(rt.store) == 0:
        return {"error": "No schema available in this review session (pure static review)"}
    name = inp.get("table", "")
    table = rt.store.get(name)
    if table is None:
        return {"error": f"Table '{name}' not found in the loaded schema"}
    return {
        "table": table.full_name,
        "comment": table.comment,
        "partitioned": table.is_partitioned,
        "partition_columns": [
            {"name": c.name, "type": c.dtype, "comment": c.comment}
            for c in table.partition_columns
        ],
        "columns": [
            {"name": c.name, "type": c.dtype, "comment": c.comment}
            for c in table.columns
        ],
    }


def _tool_lineage_impact(inp: dict[str, Any], rt: SQLReviewRuntime) -> dict[str, Any]:
    graph = rt.lineage_graph
    if graph is None:
        from .lineage_context import get_lineage_graph

        graph, hint = get_lineage_graph()
        if graph is None:
            return {"error": hint}

    try:
        depth = max(1, min(int(inp.get("depth") or 3), 10))
    except (TypeError, ValueError):
        depth = 3

    explicit = str(inp.get("table") or "").strip()
    targets = [explicit] if explicit else extract_table_lineage(rt.sql).targets
    if not targets:
        return {
            "error": "该 SQL 没有写入目标表（非 INSERT/CTAS），无需下游影响分析；"
                     "也可通过 table 参数手动指定表名"
        }

    impact: dict[str, Any] = {}
    for target in targets:
        chain = graph.downstream_of(target, depth=depth)
        if chain.missing_root:
            impact[target] = {"found": False, "message": f"血缘图中不存在表 {target}"}
            continue
        affected = [n for name, n in sorted(chain.nodes.items()) if name != chain.root]
        sla = [
            {"table": n.name, "sla_time": n.sla_time}
            for n in affected if n.is_sla
        ]
        entry: dict[str, Any] = {
            "found": True,
            "downstream_count": len(affected),
            "sla_affected": sla,
            "downstream": [
                {"table": n.name, "layer": n.layer, "is_sla": n.is_sla}
                for n in affected[:_IMPACT_MAX_TABLES]
            ],
            "truncated": chain.truncated,
        }
        if len(affected) > _IMPACT_MAX_TABLES:
            entry["note"] = f"下游表过多，仅列出前 {_IMPACT_MAX_TABLES} 个"
        impact[target] = entry
    return {"success": True, "depth": depth, "impact": impact}


def _parse_llm_finding(raw: dict[str, Any]) -> Finding | None:
    try:
        severity = Severity(str(raw.get("severity", "")).lower())
    except ValueError:
        return None
    category = str(raw.get("category", "")).strip()
    if category not in CHECK_CATALOG:
        category = "readability"
    description = str(raw.get("description", "")).strip()
    if not description:
        return None
    return Finding(
        severity=severity,
        category=category,
        description=description,
        location=str(raw.get("location") or "全局").strip() or "全局",
        impact=str(raw.get("impact") or "").strip(),
        suggestion=str(raw.get("suggestion") or "").strip(),
        source="llm",
    )


def _merge_findings(
    lint: list[Finding], llm: list[Finding]
) -> list[Finding]:
    """Linter findings first; drop LLM findings duplicating (category, location)."""
    seen = {(f.category, f.location) for f in lint}
    merged = list(lint)
    for f in llm:
        if (f.category, f.location) in seen:
            continue
        seen.add((f.category, f.location))
        merged.append(f)
    return merged


def _tool_submit_review(inp: dict[str, Any], rt: SQLReviewRuntime) -> dict[str, Any]:
    raw_findings = inp.get("findings", [])
    if not isinstance(raw_findings, list):
        return {"error": "findings must be an array"}

    llm_findings = [f for f in (_parse_llm_finding(r) for r in raw_findings if isinstance(r, dict)) if f]

    if not rt.lint_findings:
        rt.lint_findings = lint_sql(rt.sql, rt.dialect, store=rt.store, config=rt.config)

    merged = _merge_findings(rt.lint_findings, llm_findings)
    report = ReviewReport(
        findings=merged,
        summary=str(inp.get("summary") or "").strip(),
        dialect=rt.dialect,
        lineage=extract_table_lineage(rt.sql, store=rt.store),
    )
    rt.report = report
    rt.last_report = render_report(report)
    return {"success": True, "report": rt.last_report}


_TOOL_HANDLERS = {
    "lint_sql": _tool_lint_sql,
    "get_table_schema": _tool_get_table_schema,
    "lineage_impact": _tool_lineage_impact,
    "submit_review": _tool_submit_review,
}


def execute_review_tool(
    name: str, tool_input: dict[str, Any], runtime: SQLReviewRuntime
) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = handler(tool_input, runtime)
    except Exception as exc:
        result = {"error": f"Tool '{name}' failed: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)
