"""Skew finding model and report rendering.

The report has a fixed shape: verdict summary, severity-grouped finding
tables, an engine-hint section, and the 优化点说明 table (# / 优化点 /
原写法 / 优化后 / 预期收益) so static-only and LLM-assisted runs look
the same to the reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .i18n import dsk, normalize_lang


class Severity(str, Enum):
    HIGH = "high"        # 高倾斜风险（强烈建议修复）
    MEDIUM = "medium"    # 潜在倾斜（建议排查）
    LOW = "low"          # 优化建议（可选）


# Fixed catalog of skew categories (zh / en labels).
SKEW_CATALOG: dict[str, dict[str, str]] = {
    "count_distinct": {"zh": "COUNT(DISTINCT) 单点聚合", "en": "COUNT(DISTINCT) single-point aggregation"},
    "multi_count_distinct": {"zh": "多重 COUNT(DISTINCT)", "en": "Multiple COUNT(DISTINCT)"},
    "global_distinct": {"zh": "全局 DISTINCT 去重", "en": "Global DISTINCT dedup"},
    "union_dedup": {"zh": "UNION 隐式去重", "en": "UNION implicit dedup"},
    "global_orderby": {"zh": "全局 ORDER BY", "en": "Global ORDER BY"},
    "join_cartesian": {"zh": "笛卡尔积 / 缺失关联条件", "en": "Cartesian product / missing join condition"},
    "join_null_key": {"zh": "JOIN 键 NULL 值倾斜", "en": "NULL-heavy join key"},
    "join_key_expr": {"zh": "JOIN 键函数 / 类型转换", "en": "Function / cast on join key"},
    "join_hint": {"zh": "大小表 JOIN 未广播", "en": "Small-table join without broadcast"},
    "window_no_partition": {"zh": "窗口函数无分区", "en": "Window function without PARTITION BY"},
    "dynamic_partition": {"zh": "动态分区写入倾斜", "en": "Dynamic partition insert skew"},
    "too_many_joins": {"zh": "JOIN 过多", "en": "Too many joins"},
    "rand_in_join": {"zh": "JOIN 条件含非确定函数", "en": "Non-deterministic function in join condition"},
    "engine_hint": {"zh": "引擎参数建议", "en": "Engine-level hint"},
    "llm": {"zh": "LLM 语义分析", "en": "LLM semantic analysis"},
}


def category_label(category: str, lang: str) -> str:
    lang = normalize_lang(lang)
    entry = SKEW_CATALOG.get(category)
    if not entry:
        return category
    return entry.get(lang) or entry["zh"]


@dataclass
class SkewFinding:
    severity: Severity
    category: str            # key into SKEW_CATALOG
    location: str            # e.g. "行 12" / "line 12" (already localized at render)
    line: int = 0            # 1-based source line, 0 = whole script
    key: str = ""            # rule key into detector.RULES (empty for LLM findings)
    args: dict = field(default_factory=dict)
    # Pre-rendered texts (used for LLM findings; rule findings render from RULES)
    description: str = ""
    impact: str = ""
    suggestion: str = ""
    before: str = ""         # 原写法 snippet
    after: str = ""          # 优化后 snippet
    benefit: str = ""        # 预期收益
    source: str = "static"   # "static" or "llm"

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "location": self.location,
            "description": self.description,
            "impact": self.impact,
            "suggestion": self.suggestion,
            "before": self.before,
            "after": self.after,
            "benefit": self.benefit,
            "source": self.source,
        }


@dataclass
class SkewReport:
    findings: list[SkewFinding] = field(default_factory=list)
    dialect: str = "spark"
    statement_count: int = 1
    engine_hints: list[str] = field(default_factory=list)
    optimized_sql: str = ""
    consistency_notes: str = ""
    output_file: str = ""

    @property
    def high(self) -> list[SkewFinding]:
        return [f for f in self.findings if f.severity == Severity.HIGH]

    @property
    def medium(self) -> list[SkewFinding]:
        return [f for f in self.findings if f.severity == Severity.MEDIUM]

    @property
    def low(self) -> list[SkewFinding]:
        return [f for f in self.findings if f.severity == Severity.LOW]


def _md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", "<br>")


def _code(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    return "`" + text.replace("`", "'").replace("|", "\\|").replace("\n", " ") + "`"


def _location(f: SkewFinding, lang: str) -> str:
    if f.line > 0:
        return dsk(lang, "rpt_line").format(n=f.line)
    return f.location or "-"


def _findings_table(findings: list[SkewFinding], lang: str) -> str:
    header = (
        f"| {dsk(lang, 'rpt_col_idx')} | {dsk(lang, 'rpt_col_category')} | "
        f"{dsk(lang, 'rpt_col_location')} | {dsk(lang, 'rpt_col_desc')} | "
        f"{dsk(lang, 'rpt_col_impact')} | {dsk(lang, 'rpt_col_suggestion')} |\n"
        "|---|---|---|---|---|---|\n"
    )
    rows = []
    for i, f in enumerate(findings, 1):
        rows.append(
            f"| {i} | {category_label(f.category, lang)} | {_location(f, lang)} | "
            f"{_md_escape(f.description)} | {_md_escape(f.impact)} | "
            f"{_md_escape(f.suggestion)} |"
        )
    return header + "\n".join(rows)


def render_optimization_table(findings: list[SkewFinding], lang: str) -> str:
    """The fixed 优化点说明 table: # / 优化点 / 原写法 / 优化后 / 预期收益."""
    rows = [f for f in findings if f.before or f.after]
    if not rows:
        return ""
    header = (
        f"| {dsk(lang, 'rpt_col_idx')} | {dsk(lang, 'rpt_col_point')} | "
        f"{dsk(lang, 'rpt_col_before')} | {dsk(lang, 'rpt_col_after')} | "
        f"{dsk(lang, 'rpt_col_benefit')} |\n"
        "|---|---|---|---|---|\n"
    )
    body = []
    for i, f in enumerate(rows, 1):
        point = f.description or category_label(f.category, lang)
        body.append(
            f"| {i} | {_md_escape(point)} | {_code(f.before)} | "
            f"{_code(f.after)} | {_md_escape(f.benefit)} |"
        )
    return header + "\n".join(body)


def render_report(report: SkewReport, lang: str = "zh") -> str:
    """Render the full markdown report in the requested language."""
    lang = normalize_lang(lang)
    parts: list[str] = [dsk(lang, "rpt_title"), ""]
    parts.append(
        f"- **{dsk(lang, 'rpt_dialect')}**: {report.dialect}  "
        f"- **{dsk(lang, 'rpt_stmt_count')}**: {report.statement_count}"
    )
    parts.append("")

    # Summary verdict
    parts.append(dsk(lang, "rpt_summary"))
    if report.high:
        parts.append(dsk(lang, "rpt_verdict_high").format(n=len(report.high)))
    elif report.medium:
        parts.append(dsk(lang, "rpt_verdict_medium").format(n=len(report.medium)))
    else:
        parts.append(dsk(lang, "rpt_verdict_clean"))
    parts.append("")

    # Findings grouped by severity
    parts.append(dsk(lang, "rpt_findings"))
    groups = (
        ("rpt_sev_high", report.high),
        ("rpt_sev_medium", report.medium),
        ("rpt_sev_low", report.low),
    )
    any_findings = False
    for title_key, group in groups:
        if not group:
            continue
        any_findings = True
        parts.append(f"### {dsk(lang, title_key)}")
        parts.append(_findings_table(group, lang))
        parts.append("")
    if not any_findings:
        parts.append(dsk(lang, "rpt_no_findings"))
        parts.append("")

    # Engine-level hints
    if report.engine_hints:
        parts.append(dsk(lang, "rpt_engine_hints"))
        for hint in report.engine_hints:
            parts.append(f"- {hint}")
        parts.append("")

    # Optimization points table
    opt_table = render_optimization_table(report.findings, lang)
    if opt_table:
        parts.append(dsk(lang, "rpt_opt_title"))
        parts.append(opt_table)
        parts.append("")

    # Consistency + output file (LLM runs)
    if report.consistency_notes:
        parts.append(dsk(lang, "rpt_consistency"))
        parts.append(report.consistency_notes.strip())
        parts.append("")
    if report.output_file:
        parts.append(f"📄 {dsk(lang, 'rpt_optimized_file')}: `{report.output_file}`")
        parts.append("")

    return "\n".join(parts).strip() + "\n"
