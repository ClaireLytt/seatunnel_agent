"""Render a Diagnosis as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from seatunnel_agent.common.utils import normalize_lang

from .diagnoser import Diagnosis, Finding
from .i18n import tp

_SEV_MARK = {"critical": "🟥", "error": "🟧", "warn": "🟨"}


def _t(f: Finding, field: str, lang: str) -> str:
    return getattr(f, f"{field}_{'en' if lang == 'en' else 'zh'}")


def _finding_block(f: Finding, lang: str, heading: str) -> list[str]:
    mark = _SEV_MARK.get(f.severity, "•")
    lines = [f"### {mark} {heading}: {_t(f, 'title', lang)} "
             f"({f.engine} · {f.severity})",
             f"- {tp(lang, 'rpt_cause')}: {_t(f, 'cause', lang)}",
             f"- {tp(lang, 'rpt_fix')}: {_t(f, 'fix', lang)}",
             f"- {tp(lang, 'rpt_count')}: {f.count}"
             + (f" · {tp(lang, 'rpt_first')}: {f.first_ts}" if f.first_ts
                else "")]
    files = " · ".join(f"`{path}`×{n}" for path, n in
                       sorted(f.files.items(), key=lambda kv: -kv[1])[:5])
    if files:
        lines.append(f"- {tp(lang, 'rpt_files')}: {files}")
    if f.patch:
        lines.append(f"- {tp(lang, 'rpt_patch')}:")
        lines.append("```text\n" + f.patch + "\n```")
    if f.sample:
        lines.append(f"- {tp(lang, 'rpt_evidence')}:")
        lines.append("```text\n" + f.sample + "\n```")
    lines.append("")
    return lines


def render_markdown(diag: Diagnosis, lang: str = "zh",
                    top: int = 10) -> str:
    lang = normalize_lang(lang)
    c = diag.counts()
    engines = (" · ".join(f"{e}×{n}" for e, n in
                          sorted(diag.engines.items(), key=lambda kv: -kv[1]))
               or tp(lang, "rpt_engine_unknown"))
    lines = [f"## 🩺 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_root')} `{diag.root}` · "
             f"{tp(lang, 'rpt_engines')}: {engines}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 files=diag.files_scanned, lines=diag.lines_scanned,
                 events=diag.events, findings=c["findings"],
                 critical=c["critical"], error=c["error"], warn=c["warn"],
                 unmatched=c["unmatched"]) + "**",
             ""]
    if not diag.findings and not diag.unmatched:
        lines.append(tp(lang, "rpt_clean"))
        lines.append("")
    if diag.findings:
        shown = diag.findings[:top]
        lines.extend(_finding_block(shown[0], lang, tp(lang, "rpt_primary")))
        for i, f in enumerate(shown[1:], start=2):
            lines.extend(_finding_block(f, lang,
                                        f"{tp(lang, 'rpt_findings')} {i}"))
    if diag.unmatched:
        lines.append(f"### ❓ {tp(lang, 'rpt_unmatched')}")
        lines.append(tp(lang, "rpt_unmatched_hint"))
        for cl in diag.unmatched[:top]:
            head = cl.exception or cl.template or "(no message)"
            lines.append(f"- `{head}` ×{cl.count}")
        lines.append("")
    if diag.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in diag.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def diagnosis_to_dict(diag: Diagnosis, top: int | None = None,
                      ) -> dict[str, Any]:
    findings = diag.findings if top is None else diag.findings[:top]
    unmatched = diag.unmatched if top is None else diag.unmatched[:top]
    return {
        "root": diag.root,
        "engines": dict(diag.engines),
        "files_scanned": diag.files_scanned,
        "lines_scanned": diag.lines_scanned,
        "counts": diag.counts(),
        "findings": [f.to_dict() for f in findings],
        "unmatched": [c.to_dict() for c in unmatched],
        "warnings": list(diag.warnings),
    }
