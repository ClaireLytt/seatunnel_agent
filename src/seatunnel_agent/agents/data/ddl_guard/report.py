"""Markdown rendering for the migration-guard report (zh/en)."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK

from .guard import GuardReport

_T = {
    "zh": {
        "title": "# 迁移守卫报告",
        "scope": "范围",
        "stmts": "语句数",
        "irreversible": "不可逆",
        "clean": "迁移脚本安全——没有危险的 DDL 操作。",
        "findings": "## 危险操作",
        "undo": "## 回滚脚本",
        "warnings": "## 解析警告",
        "kind": {"drop_table": "删表", "drop_column": "删列",
                 "truncate_table": "清空表", "type_narrowing": "类型收窄",
                 "type_change": "类型变更", "rename_table": "表重命名",
                 "rename_column": "列重命名",
                 "not_null_no_default": "NOT NULL 无默认值",
                 "live_grants": "授权未回收"},
        "irrev_mark": "（不可逆）",
    },
    "en": {
        "title": "# Migration Guard Report",
        "scope": "scope",
        "stmts": "statements",
        "irreversible": "irreversible",
        "clean": "The migration is safe - no dangerous DDL operations.",
        "findings": "## Dangerous operations",
        "undo": "## Rollback script",
        "warnings": "## Parse warnings",
        "kind": {"drop_table": "drop table", "drop_column": "drop column",
                 "truncate_table": "truncate table",
                 "type_narrowing": "type narrowing",
                 "type_change": "type change",
                 "rename_table": "table rename",
                 "rename_column": "column rename",
                 "not_null_no_default": "NOT NULL without default",
                 "live_grants": "live grants left behind"},
        "irrev_mark": " (irreversible)",
    },
}

def render_markdown(report: GuardReport, lang: str = "zh") -> str:
    t = _T.get(lang, _T["zh"])
    c = report.counts()
    lines = [t["title"], "",
             f"- {t['scope']}: `{report.root}` · {report.dialect}",
             f"- {t['stmts']}: {report.statements_seen} · "
             f"high {c['high']} · medium {c['medium']} · "
             f"{t['irreversible']}: {c['irreversible']}", ""]
    if c["total"] == 0:
        lines += [t["clean"], ""]
    if report.findings:
        lines += [t["findings"], ""]
        for f in sorted(report.findings,
                        key=lambda x: ("high medium low".split().index(
                            x.severity), x.table, x.column)):
            col = f"`.{f.column}`" if f.column else ""
            mark = "" if f.reversible else t["irrev_mark"]
            lines.append(f"- {SEVERITY_MARK[f.severity]} "
                         f"[{t['kind'][f.kind]}] `{f.table}`{col}{mark} — "
                         f"{f.detail}")
        lines.append("")
    if report.undo_sql:
        lines += [t["undo"], "", "```sql", report.undo_sql.rstrip(), "```", ""]
    if report.warnings:
        lines += [t["warnings"], ""]
        lines += [f"- {w}" for w in report.warnings]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
