"""Review finding model and CR report rendering.

The report format is fixed (see resources/SKILL.md): severity-grouped
markdown tables plus check statistics and an overall verdict, so every
review — static-only or LLM-assisted — looks the same to the reader.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, "") or default))
    except ValueError:
        return default


# max column-lineage rows shown in the rendered report
LINEAGE_DISPLAY_LIMIT = _env_int("SQLREVIEW_LINEAGE_DISPLAY_LIMIT", 15)


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


_LINE_LOC_RE = re.compile(r"行\s*(\d+)")
_EN_LINE_LOC_RE = re.compile(r"\bline\s*(\d+)", re.IGNORECASE)


def _loc(location: str, lang: str) -> str:
    """Localize a finding location for display ("行 6" <-> "Line 6")."""
    if lang == "en":
        loc = _LINE_LOC_RE.sub(lambda m: f"Line {m.group(1)}", location)
        return loc.replace("全局", "Global")
    loc = _EN_LINE_LOC_RE.sub(lambda m: f"行 {m.group(1)}", location)
    return re.sub(r"\bglobal\b", "全局", loc, flags=re.IGNORECASE)


def render_report(report: ReviewReport, lang: str = "zh") -> str:
    """Render the CR report in the fixed markdown format (zh or en chrome)."""
    from .i18n import sr

    def t(key: str) -> str:
        return sr(lang, key)

    sep = ": " if lang == "en" else "："
    parts: list[str] = [t("sr_report_title")]

    parts.append(f"\n{t('sr_sec_critical')}\n")
    if report.criticals:
        rows = [
            [str(i), f.description, _loc(f.location, lang), f.impact, f.suggestion]
            for i, f in enumerate(report.criticals, 1)
        ]
        parts.append(_table(
            [t("sr_h_no"), t("sr_h_desc"), t("sr_h_loc"), t("sr_h_impact"), t("sr_h_fix")],
            rows))
    else:
        parts.append(t("sr_none"))

    parts.append(f"\n{t('sr_sec_risk')}\n")
    if report.risks:
        rows = [
            [str(i), f.description, _loc(f.location, lang), f.impact, f.suggestion]
            for i, f in enumerate(report.risks, 1)
        ]
        parts.append(_table(
            [t("sr_h_no"), t("sr_h_desc"), t("sr_h_loc"), t("sr_h_risk"), t("sr_h_opt")],
            rows))
    else:
        parts.append(t("sr_none"))

    parts.append(f"\n{t('sr_sec_suggestion')}\n")
    if report.suggestions:
        if lang == "en":
            fmt = lambda f: (f"- {f.description} ({f.suggestion})"  # noqa: E731
                             if f.suggestion else f"- {f.description}")
        else:
            fmt = lambda f: (f"- {f.description}（{f.suggestion}）"  # noqa: E731
                             if f.suggestion else f"- {f.description}")
        parts.append("\n".join(fmt(f) for f in report.suggestions))
    else:
        parts.append(t("sr_none"))

    if report.lineage:
        lin = report.lineage
        lineage_md = (
            f"\n{t('sr_sec_lineage')}\n"
            f"- {t('sr_lin_sources')}{sep}"
            f"{', '.join(lin.sources) if lin.sources else t('sr_none')}\n"
            f"- {t('sr_lin_targets')}{sep}"
            f"{', '.join(lin.targets) if lin.targets else t('sr_lin_none_target')}"
        )
        if lin.columns:
            col_lines = [f"- {t('sr_lin_columns')}"]
            for col in lin.columns[:LINEAGE_DISPLAY_LIMIT]:
                agg = t("sr_lin_agg") if col.get("aggregated") else ""
                col_lines.append(f"  - {col['output']} ← {col['source']}{agg}")
            lineage_md += "\n" + "\n".join(col_lines)
        parts.append(lineage_md)

    s = report.stats()
    parts.append(
        f"\n{t('sr_sec_stats')}\n"
        f"- {t('sr_stats_total')}{sep}{s['total']}\n"
        f"- {t('sr_stats_passed')}{sep}{s['passed']}\n"
        f"- {t('sr_stats_problems')}{sep}{s['problems']}\n"
        f"- {t('sr_stats_risks')}{sep}{s['risks']}"
    )

    parts.append(f"\n{t('sr_sec_verdict')}\n")
    parts.append(report.summary or _default_summary(report, lang))

    return "\n".join(parts)


def _default_summary(report: ReviewReport, lang: str = "zh") -> str:
    from .i18n import sr
    if report.criticals:
        return sr(lang, "sr_sum_critical").format(n=len(report.criticals))
    if report.risks:
        return sr(lang, "sr_sum_risk").format(n=len(report.risks))
    return sr(lang, "sr_sum_pass")
