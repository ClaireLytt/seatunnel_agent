"""Review finding model and CR report rendering.

The report format is fixed (see resources/SKILL.md): severity-grouped
markdown tables plus check statistics and an overall verdict, so every
review — static-only or LLM-assisted — looks the same to the reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"    # 严重问题（必须修复）
    RISK = "risk"            # 潜在风险（建议修复）
    SUGGESTION = "suggestion"  # 优化建议（可选）


# The fixed catalog of check items. 检查统计's 检查项总数 is the size of
# this catalog; a category "passes" when no finding references it.
CHECK_CATALOG: dict[str, str] = {
    "join_condition": "JOIN 关联条件与字段准确性",
    "join_cartesian": "JOIN 类型一致性 / 多对多与笛卡尔积",
    "where_syntax": "WHERE 条件语法与 NULL 判断",
    "where_partition": "时间范围与分区条件书写",
    "groupby_completeness": "GROUP BY 字段完整性",
    "aggregate_functions": "聚合函数使用正确性",
    "calculation": "计算逻辑（NULL/除零/金额精度/比例）",
    "null_handling": "空值处理（COALESCE/NVL/空字符串）",
    "dedup": "去重逻辑与主键唯一性",
    "type_cast": "数据类型转换与比较",
    "partition_pruning": "分区裁剪与分区粒度",
    "data_skew": "数据倾斜（热点 Key / 大表 JOIN）",
    "resource_usage": "资源使用（全表扫描/临时表/增量）",
    "readability": "代码规范与可读性",
    "time_boundary": "时间边界逻辑（跨天/时区/月末/闰年）",
}


@dataclass
class Finding:
    severity: Severity
    category: str          # key into CHECK_CATALOG
    description: str       # 问题描述
    location: str          # 代码位置, e.g. "行 6"
    impact: str            # 影响范围 / 风险说明
    suggestion: str        # 修复建议 / 优化建议
    source: str = "linter"  # "linter" or "llm"

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "description": self.description,
            "location": self.location,
            "impact": self.impact,
            "suggestion": self.suggestion,
            "source": self.source,
        }


@dataclass
class TableLineage:
    """Table + column lineage: which tables feed the statement, which it
    writes, and (best-effort) how each output column is derived."""
    sources: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.sources or self.targets)

    def to_dict(self) -> dict:
        doc: dict = {"sources": self.sources, "targets": self.targets}
        if self.columns:
            doc["columns"] = self.columns
        return doc


@dataclass
class ReviewReport:
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    dialect: str = "hive"
    lineage: TableLineage | None = None

    @property
    def criticals(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    @property
    def risks(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.RISK]

    @property
    def suggestions(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.SUGGESTION]

    def stats(self) -> dict[str, int]:
        flagged = {
            f.category for f in self.findings
            if f.severity in (Severity.CRITICAL, Severity.RISK)
            and f.category in CHECK_CATALOG
        }
        total = len(CHECK_CATALOG)
        return {
            "total": total,
            "passed": total - len(flagged),
            "problems": len(self.criticals),
            "risks": len(self.risks),
        }


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("-----" for _ in headers) + "|",
    ]
    for row in rows:
        cells = [c.replace("|", "\\|").replace("\n", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(report: ReviewReport) -> str:
    """Render the CR report in the fixed markdown format."""
    parts: list[str] = ["## CR 报告"]

    parts.append("\n### 🔴 严重问题（必须修复）\n")
    if report.criticals:
        rows = [
            [str(i), f.description, f.location, f.impact, f.suggestion]
            for i, f in enumerate(report.criticals, 1)
        ]
        parts.append(_table(["序号", "问题描述", "代码位置", "影响范围", "修复建议"], rows))
    else:
        parts.append("无")

    parts.append("\n### 🟡 潜在风险（建议修复）\n")
    if report.risks:
        rows = [
            [str(i), f.description, f.location, f.impact, f.suggestion]
            for i, f in enumerate(report.risks, 1)
        ]
        parts.append(_table(["序号", "问题描述", "代码位置", "风险说明", "优化建议"], rows))
    else:
        parts.append("无")

    parts.append("\n### 🟢 优化建议（可选）\n")
    if report.suggestions:
        parts.append("\n".join(f"- {f.description}（{f.suggestion}）" if f.suggestion else f"- {f.description}"
                               for f in report.suggestions))
    else:
        parts.append("无")

    if report.lineage:
        lin = report.lineage
        lineage_md = (
            "\n### 🔗 表级血缘\n"
            f"- 来源表：{', '.join(lin.sources) if lin.sources else '无'}\n"
            f"- 目标表：{', '.join(lin.targets) if lin.targets else '无（仅查询）'}"
        )
        if lin.columns:
            col_lines = ["- 列级血缘："]
            for col in lin.columns[:15]:
                agg = "（聚合）" if col.get("aggregated") else ""
                col_lines.append(f"  - {col['output']} ← {col['source']}{agg}")
            lineage_md += "\n" + "\n".join(col_lines)
        parts.append(lineage_md)

    s = report.stats()
    parts.append(
        "\n### 📊 检查统计\n"
        f"- 检查项总数：{s['total']}\n"
        f"- 通过：{s['passed']}\n"
        f"- 问题：{s['problems']}\n"
        f"- 风险：{s['risks']}"
    )

    parts.append("\n### 💡 总体评价\n")
    parts.append(report.summary or _default_summary(report))

    return "\n".join(parts)


def _default_summary(report: ReviewReport) -> str:
    if report.criticals:
        return (
            f"代码存在 {len(report.criticals)} 个严重问题，会导致 SQL 执行错误或结果不正确，"
            "必须修复后才能上线。"
        )
    if report.risks:
        return (
            f"代码无严重问题，但存在 {len(report.risks)} 个潜在风险，"
            "建议按优化建议修复后再上线。"
        )
    return "代码检查通过，未发现明显问题。"
