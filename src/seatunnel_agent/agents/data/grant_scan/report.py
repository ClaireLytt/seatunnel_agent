"""Markdown rendering for the grant-surface report (zh/en)."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK

from .scanner import GrantReport

_T = {
    "zh": {
        "title": "# 权限面报告",
        "scope": "范围",
        "surface": "授权语句",
        "net": "净授权面",
        "clean": "授权面干净——没有公开授权、宽权限或敏感表外授。",
        "sensitive": "## 命中 PII 的表",
        "findings": "## 发现",
        "effective": "## 净授权清单",
        "warnings": "## 解析警告",
        "kind": {"public_grant": "公开授权", "sensitive_grant": "敏感表授权",
                 "broad_privilege": "宽权限", "wide_scope": "宽范围"},
    },
    "en": {
        "title": "# Grant Surface Report",
        "scope": "scope",
        "surface": "grant statements",
        "net": "net surface",
        "clean": "The grant surface is clean - no public grants, broad "
                 "privileges or sensitive-table exposure.",
        "sensitive": "## PII-flagged tables",
        "findings": "## Findings",
        "effective": "## Net grants",
        "warnings": "## Parse warnings",
        "kind": {"public_grant": "public grant",
                 "sensitive_grant": "sensitive-table grant",
                 "broad_privilege": "broad privilege",
                 "wide_scope": "wide scope"},
    },
}

def render_markdown(report: GrantReport, lang: str = "zh") -> str:
    t = _T.get(lang, _T["zh"])
    c = report.counts()
    lines = [t["title"], "",
             f"- {t['scope']}: `{report.root}` · {report.dialect}",
             f"- {t['surface']}: GRANT {report.grants_seen} · "
             f"REVOKE {report.revokes_seen} · {t['net']}: "
             f"{len(report.effective)} · "
             f"high {c['high']} · medium {c['medium']}", ""]
    if c["total"] == 0:
        lines += [t["clean"], ""]
    if report.sensitive_tables:
        lines += [t["sensitive"], ""]
        lines += [f"- `{s}`" for s in report.sensitive_tables]
        lines.append("")
    if report.findings:
        lines += [t["findings"], ""]
        for f in sorted(report.findings,
                        key=lambda x: ("high medium low".split().index(
                            x.severity), x.target, x.principal)):
            privs = ", ".join(f.privileges)
            lines.append(f"- {SEVERITY_MARK[f.severity]} "
                         f"[{t['kind'][f.kind]}] `{f.target}` → "
                         f"`{f.principal}` ({privs}) — {f.detail}")
        lines.append("")
    if report.effective:
        lines += [t["effective"], ""]
        for g in report.effective:
            lines.append(f"- `{g.target}` → `{g.principal}`: "
                         f"{', '.join(g.privileges)} ({g.scope})")
        lines.append("")
    if report.warnings:
        lines += [t["warnings"], ""]
        lines += [f"- {w}" for w in report.warnings]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
