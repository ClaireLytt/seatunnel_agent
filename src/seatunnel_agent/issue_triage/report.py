# -*- coding: utf-8 -*-
"""Markdown rendering for triage results."""

from __future__ import annotations

from .engine import TriageResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## Issue Triage",
        "labels": "Labels",
        "dups": "Possible duplicates",
        "prio": "Priority",
        "draft": "### Draft reply",
        "none": "—",
        "unparsed": ("> ⚠️ The agent's final answer was not valid JSON — "
                     "raw text below."),
        "steps": "steps",
    },
    "zh": {
        "title": "## Issue 分诊",
        "labels": "标签",
        "dups": "疑似重复",
        "prio": "优先级",
        "draft": "### 草拟回复",
        "none": "—",
        "unparsed": "> ⚠️ Agent 最终回答不是合法 JSON — 原文如下。",
        "steps": "步",
    },
}


def render_markdown(result: TriageResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines = [t["title"], ""]
    if not result.parsed:
        lines += [t["unparsed"], "", result.raw_reply or t["none"]]
        return "\n".join(lines)
    dups = ", ".join(f"#{n}" for n in result.duplicates) or t["none"]
    labels = ", ".join(f"`{x}`" for x in result.labels) or t["none"]
    lines.append(f"- **{t['labels']}**: {labels}")
    lines.append(f"- **{t['prio']}**: {result.priority}")
    lines.append(f"- **{t['dups']}**: {dups}")
    lines.append(f"- 🔧 {len(result.steps)} {t['steps']}")
    if result.draft:
        lines += ["", t["draft"], "", result.draft]
    return "\n".join(lines)
