# -*- coding: utf-8 -*-
"""Markdown rendering for orchestrator runs (CLI / API report)."""

from __future__ import annotations

from .engine import OrchestratorResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "steps_title": "### Tool steps",
        "step_line": "{i}. `{tool}` · {ms} ms{err}",
        "err_mark": " · ⚠️ failed",
        "truncated": "> ⚠️ Step limit reached — the answer summarizes partial results.",
        "answer_title": "### Answer",
    },
    "zh": {
        "steps_title": "### 工具调用",
        "step_line": "{i}. `{tool}` · {ms} ms{err}",
        "err_mark": " · ⚠️ 失败",
        "truncated": "> ⚠️ 已达步数上限 — 回答基于已有的部分结果。",
        "answer_title": "### 回答",
    },
}


def render_markdown(result: OrchestratorResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines: list[str] = []
    if result.steps:
        lines.append(t["steps_title"])
        for i, s in enumerate(result.steps, 1):
            lines.append(t["step_line"].format(
                i=i, tool=s.tool, ms=s.elapsed_ms,
                err=t["err_mark"] if s.error else ""))
        lines.append("")
    if result.truncated:
        lines += [t["truncated"], ""]
    lines.append(t["answer_title"])
    lines.append(result.reply or "_(empty)_")
    return "\n".join(lines)
