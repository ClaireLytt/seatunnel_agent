# -*- coding: utf-8 -*-
"""Bilingual markdown report for secret scans."""

from __future__ import annotations

from .scanner import ScanResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


from typing import Any

_I18N: dict[str, dict[str, Any]] = {
    "en": {
        "title": "## Secret Scan",
        "stats": ("files scanned {scanned} · skipped {skipped} · findings "
                  "**{total}** (high {high} / medium {medium} / low {low})"),
        "clean": "✅ No secrets found.",
        "header": "Severity | Rule | File | Line | Preview (masked)",
        "sev": {"high": "🔴 high", "medium": "🟠 medium", "low": "🟡 low"},
        "disclaimer": ("> Previews are masked — the scanner never echoes a "
                       "full secret. Suppress a line with "
                       "`secretscan:ignore`, a rule/path via "
                       "`.secretscan.yaml`."),
    },
    "zh": {
        "title": "## 敏感凭证扫描",
        "stats": ("扫描文件 {scanned} · 跳过 {skipped} · 发现 **{total}** 处"
                  "(高危 {high} / 中危 {medium} / 低危 {low})"),
        "clean": "✅ 未发现疑似凭证。",
        "header": "严重度 | 规则 | 文件 | 行 | 预览(已脱敏)",
        "sev": {"high": "🔴 高危", "medium": "🟠 中危", "low": "🟡 低危"},
        "disclaimer": ("> 预览已脱敏 — 扫描器绝不回显完整凭证。单行可用 "
                       "`secretscan:ignore` 豁免,规则/路径用 "
                       "`.secretscan.yaml` 配置。"),
    },
}


def render_markdown(result: ScanResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    sev = result.severities
    lines = [t["title"], ""]
    lines.append(t["stats"].format(
        scanned=result.files_scanned, skipped=result.files_skipped,
        total=len(result.findings), **sev))
    if not result.findings:
        lines += ["", t["clean"]]
        return "\n".join(lines)
    lines += ["", "| " + t["header"] + " |", "|---|---|---|---|---|"]
    for f in result.findings:
        name = f.rule_name_zh if lang == "zh" else f.rule_name_en
        lines.append(f"| {t['sev'][f.severity]} | {name} | `{f.file}` "
                     f"| {f.line} | `{f.masked}` |")
    lines += ["", t["disclaimer"]]
    return "\n".join(lines)
