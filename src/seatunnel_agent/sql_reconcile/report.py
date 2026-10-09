# -*- coding: utf-8 -*-
"""Render a ReconcileReport as markdown (zh/en) or a plain dict."""

from __future__ import annotations

from typing import Any

from .i18n import RECONCILE_I18N, normalize_lang
from .reconciler import ReconcileReport

_CAT_ORDER = ["source", "join", "filter", "time_range", "aggregation",
              "dedup", "limit", "output"]
_SEV_MARK = {"critical": "🔴", "risk": "🟡", "info": "ℹ️"}


def render_markdown(report: ReconcileReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = RECONCILE_I18N[lang]
    lines: list[str] = [f"# {t['rpt_title']}", ""]
    if report.parse_error:
        lines.append(t["rpt_parse_error"].format(error=report.parse_error))
        return "\n".join(lines)

    counts = report.counts()
    lines.append(f"{t['rpt_dialect']}: `{report.dialect}` · "
                 + t["rpt_stats"].format(total=len(report.findings),
                                         critical=counts["critical"],
                                         risk=counts["risk"],
                                         info=counts["info"]))
    lines.append("")
    if report.identical:
        lines += [t["rpt_identical"], "", t["rpt_disclaimer"]]
        return "\n".join(lines)

    for cat in _CAT_ORDER:
        cat_findings = [f for f in report.findings if f.category == cat]
        if not cat_findings:
            continue
        lines.append(f"## {t['cat_' + cat]}")
        for f in cat_findings:
            msg = t[f.key].format(**f.args)
            lines.append(f"- {_SEV_MARK[f.severity]} "
                         f"**{t['sev_' + f.severity]}** · {msg}")
        lines.append("")

    lines.append(f"## {t['rpt_profiles']}")
    for side, prof in ((t["rpt_side_a"], report.profile_a),
                       (t["rpt_side_b"], report.profile_b)):
        lines.append(f"### {side}")
        lines.append("```json")
        import json
        lines.append(json.dumps(prof.to_dict(), ensure_ascii=False, indent=2))
        lines.append("```")
    lines += ["", t["rpt_disclaimer"]]
    return "\n".join(lines)


def report_to_dict(report: ReconcileReport,
                   lang: str = "zh") -> dict[str, Any]:
    lang = normalize_lang(lang)
    t = RECONCILE_I18N[lang]
    findings = []
    for f in report.findings:
        d = f.to_dict()
        d["message"] = t[f.key].format(**f.args)
        findings.append(d)
    return {
        "identical": report.identical,
        "parse_error": report.parse_error,
        "dialect": report.dialect,
        "counts": report.counts(),
        "worst_level": report.worst_level(),
        "findings": findings,
        "profile_a": report.profile_a.to_dict(),
        "profile_b": report.profile_b.to_dict(),
    }
