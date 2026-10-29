"""Markdown rendering for the hygiene report (zh/en)."""

from __future__ import annotations

from .analyzer import HygieneReport

_T = {
    "zh": {
        "title": "# 数仓卫生检查报告",
        "scope": "范围",
        "tables": "血缘可见表",
        "clean": "没有发现可退役的死重——数仓很干净。",
        "orphans": "## 只写不读（孤儿产出）",
        "orphans_hint": "有人在维护这些表的产出链路，却没有任何下游读它们。",
        "dead": "## 死列（表有人读，列无人取）",
        "dead_hint": "这些列随表一起被生产与存储，但从未被任何下游 SELECT。",
        "dangling": "## 悬空定义（有 DDL、无血缘）",
        "dangling_hint": "建表语句存在，但没有任何 INSERT/SELECT 触碰过它们。",
        "warnings": "## 解析警告",
    },
    "en": {
        "title": "# Warehouse Hygiene Report",
        "scope": "scope",
        "tables": "tables in lineage",
        "clean": "No retirable dead weight found - the warehouse is clean.",
        "orphans": "## Write-only tables (orphan outputs)",
        "orphans_hint": "Someone maintains these pipelines, nothing reads them.",
        "dead": "## Dead columns (table is read, column never selected)",
        "dead_hint": "Produced and stored with the table, selected by nothing.",
        "dangling": "## Dangling definitions (DDL exists, lineage never touches it)",
        "dangling_hint": "CREATE TABLE exists; no INSERT/SELECT ever involves them.",
        "warnings": "## Parse warnings",
    },
}


def render_markdown(report: HygieneReport, lang: str = "zh") -> str:
    t = _T.get(lang, _T["zh"])
    c = report.counts()
    lines = [t["title"], "",
             f"- {t['scope']}: `{report.root}` · {report.dialect}",
             f"- {t['tables']}: {report.tables_seen} · "
             f"orphan {c['orphan_outputs']} · dead-col {c['dead_columns']} · "
             f"dangling {c['dangling_defs']}", ""]
    if c["total"] == 0:
        lines += [t["clean"], ""]
    if report.orphan_outputs:
        lines += [t["orphans"], "", t["orphans_hint"], ""]
        lines += [f"- `{i.table}`" for i in report.orphan_outputs] + [""]
    if report.dead_columns:
        lines += [t["dead"], "", t["dead_hint"], ""]
        lines += [f"- `{i.table}`.`{i.column}`" for i in report.dead_columns]
        lines += [""]
    if report.dangling_defs:
        lines += [t["dangling"], "", t["dangling_hint"], ""]
        lines += [f"- `{i.table}`" for i in report.dangling_defs] + [""]
    if report.warnings:
        lines += [t["warnings"], ""]
        lines += [f"- {w}" for w in report.warnings] + [""]
    return "\n".join(lines).rstrip() + "\n"
