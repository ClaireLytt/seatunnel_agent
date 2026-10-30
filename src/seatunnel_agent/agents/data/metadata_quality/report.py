"""Markdown rendering for the metadata-quality report (zh/en)."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK

from .checker import MetaQualityReport

_T = {
    "zh": {
        "title": "# 元数据质量报告",
        "scope": "范围",
        "tables": "检查表数",
        "clean": "全部建表语句符合规约——元数据很干净。",
        "coverage": "## 注释覆盖率",
        "findings": "## 发现",
        "warnings": "## 解析警告",
        "kind": {"missing_comment": "缺注释", "layer_naming": "分层命名",
                 "money_float": "金额用浮点", "date_string": "日期用裸 STRING",
                 "money_string": "金额用 STRING",
                 "unpartitioned_fact": "事实表无分区",
                 "missing_owner": "无负责人标注"},
    },
    "en": {
        "title": "# Metadata Quality Report",
        "scope": "scope",
        "tables": "tables checked",
        "clean": "Every CREATE TABLE follows the conventions - metadata is clean.",
        "coverage": "## Comment coverage",
        "findings": "## Findings",
        "warnings": "## Parse warnings",
        "kind": {"missing_comment": "missing comment",
                 "layer_naming": "layer naming",
                 "money_float": "money on float",
                 "date_string": "date as bare STRING",
                 "money_string": "money as STRING",
                 "unpartitioned_fact": "unpartitioned fact table",
                 "missing_owner": "missing owner"},
    },
}

def render_markdown(report: MetaQualityReport, lang: str = "zh") -> str:
    t = _T.get(lang, _T["zh"])
    c = report.counts()
    lines = [t["title"], "",
             f"- {t['scope']}: `{report.root}` · {report.dialect}",
             f"- {t['tables']}: {report.tables_checked} · "
             f"high {c['high']} · medium {c['medium']} · low {c['low']}", ""]
    if c["total"] == 0:
        lines += [t["clean"], ""]
    if report.coverage:
        lines += [t["coverage"], ""]
        for cov in report.coverage:
            lines.append(f"- `{cov.table}`: {cov.commented}/{cov.total} "
                         f"({cov.pct}%)")
        lines.append("")
    if report.findings:
        lines += [t["findings"], ""]
        for f in sorted(report.findings,
                        key=lambda x: ("high medium low".split().index(
                            x.severity), x.table, x.column)):
            col = f"`.{f.column}`" if f.column else ""
            lines.append(f"- {SEVERITY_MARK[f.severity]} "
                         f"[{t['kind'][f.kind]}] `{f.table}`{col} — {f.detail}")
        lines.append("")
    if report.warnings:
        lines += [t["warnings"], ""]
        lines += [f"- {w}" for w in report.warnings] + [""]
    return "\n".join(lines).rstrip() + "\n"
