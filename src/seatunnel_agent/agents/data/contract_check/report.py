"""Markdown rendering for the data-contract report (zh/en)."""

from __future__ import annotations

from .checker import ContractReport

_T = {
    "zh": {
        "title": "# 数据契约校验报告",
        "scope": "范围",
        "tables": "契约声明表数",
        "checked": "实际命中",
        "clean": "DDL 完全履行契约——没有违约项。",
        "findings": "## 违约项",
        "warnings": "## 解析警告",
        "kind": {"missing_table": "表缺失", "missing_column": "列缺失",
                 "type_mismatch": "类型违约", "partition_mismatch": "分区违约",
                 "missing_comment": "缺注释", "extra_column": "契约外列"},
        "expected": "期望", "actual": "实际",
    },
    "en": {
        "title": "# Data Contract Report",
        "scope": "scope",
        "tables": "tables declared",
        "checked": "matched in DDL",
        "clean": "The DDL honors the contract in full - no violations.",
        "findings": "## Violations",
        "warnings": "## Parse warnings",
        "kind": {"missing_table": "missing table",
                 "missing_column": "missing column",
                 "type_mismatch": "type violation",
                 "partition_mismatch": "partition violation",
                 "missing_comment": "missing comment",
                 "extra_column": "column outside contract"},
        "expected": "expected", "actual": "actual",
    },
}

# same severity marks as the other governance reports
_SEV_ICON = {"high": "⛔", "medium": "⚠️", "low": "🔵"}


def render_markdown(report: ContractReport, lang: str = "zh") -> str:
    t = _T.get(lang, _T["zh"])
    c = report.counts()
    lines = [t["title"], "",
             f"- {t['scope']}: `{report.root}` · {report.dialect}",
             f"- {t['tables']}: {report.tables_declared} · "
             f"{t['checked']}: {report.tables_checked} · "
             f"high {c['high']} · medium {c['medium']} · low {c['low']}", ""]
    if c["total"] == 0:
        lines += [t["clean"], ""]
    if report.findings:
        lines += [t["findings"], ""]
        for f in sorted(report.findings,
                        key=lambda x: ("high medium low".split().index(
                            x.severity), x.table, x.column)):
            col = f"`.{f.column}`" if f.column else ""
            lines.append(f"- {_SEV_ICON[f.severity]} "
                         f"[{t['kind'][f.kind]}] `{f.table}`{col} — "
                         f"{t['expected']}: {f.expected} · "
                         f"{t['actual']}: {f.actual}")
        lines.append("")
    if report.warnings:
        lines += [t["warnings"], ""]
        lines += [f"- {w}" for w in report.warnings]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
