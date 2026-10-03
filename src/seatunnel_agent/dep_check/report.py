# -*- coding: utf-8 -*-
"""Bilingual markdown report for dependency health."""

from __future__ import annotations

from .core import DepReport


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


from typing import Any

_I18N: dict[str, dict[str, Any]] = {
    "en": {
        "title": "## Dependency Health",
        "stats": ("packages {packages} · findings **{total}** "
                  "(high {high} / medium {medium} / info {info})"),
        "clean": "✅ No findings.",
        "find_header": "Severity | Category | Package | Detail",
        "pkg_title": "### Inventory",
        "pkg_header": "Package | Declared | Installed | License | Groups",
        "sev": {"high": "🔴 high", "medium": "🟠 medium", "info": "ℹ️ info"},
        "disclaimer": ("> Offline check: declared vs installed, pins and "
                       "licenses. CVE / latest-version checks need the "
                       "network and stay out of the CI gate."),
    },
    "zh": {
        "title": "## 依赖体检",
        "stats": ("依赖 {packages} 个 · 发现 **{total}** 处"
                  "(高危 {high} / 中危 {medium} / 提示 {info})"),
        "clean": "✅ 没有发现问题。",
        "find_header": "严重度 | 类别 | 包 | 说明",
        "pkg_title": "### 依赖清单",
        "pkg_header": "包 | 声明 | 实装 | License | 来源",
        "sev": {"high": "🔴 高危", "medium": "🟠 中危", "info": "ℹ️ 提示"},
        "disclaimer": ("> 离线检查:声明 vs 实装、版本钉与 License。"
                       "CVE / 最新版本需要联网,不进 CI 门禁。"),
    },
}


def render_markdown(report: DepReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    sev = report.severities
    lines = [t["title"], ""]
    lines.append(t["stats"].format(packages=len(report.packages),
                                   total=len(report.findings), **sev))
    if report.findings:
        lines += ["", "| " + t["find_header"] + " |", "|---|---|---|---|"]
        for f in report.findings:
            lines.append(f"| {t['sev'][f.severity]} | {f.category} "
                         f"| `{f.package}` | {f.detail} |")
    else:
        lines += ["", t["clean"]]
    if report.packages:
        lines += ["", t["pkg_title"], "",
                  "| " + t["pkg_header"] + " |", "|---|---|---|---|---|"]
        for p in report.packages:
            lines.append(f"| `{p['package']}` | {p['declared']} "
                         f"| {p['installed']} | {p['license']} "
                         f"| {p['groups']} |")
    lines += ["", t["disclaimer"]]
    return "\n".join(lines)
