# -*- coding: utf-8 -*-
"""Markdown rendering for code-fix runs."""

from __future__ import annotations

from .engine import CodeFixResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "ok": "## ✅ Tests green",
        "fail": "## ❌ Tests still failing",
        "steps": "### Agent steps",
        "diff": "### Diff (review before taking it)",
        "no_diff": "_(no changes were made)_",
        "workdir": "Worktree",
        "summary": "### Agent summary",
        "truncated": "> ⚠️ Step limit reached.",
    },
    "zh": {
        "ok": "## ✅ 测试已通过",
        "fail": "## ❌ 测试仍未通过",
        "steps": "### Agent 步骤",
        "diff": "### 改动 Diff(采纳前请人工审阅)",
        "no_diff": "_(没有产生任何改动)_",
        "workdir": "工作副本",
        "summary": "### Agent 总结",
        "truncated": "> ⚠️ 已达步数上限。",
    },
}


def render_markdown(result: CodeFixResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = _I18N[lang]
    lines = [t["ok"] if result.success else t["fail"], ""]
    lines.append(f"{t['workdir']}: `{result.workdir}` · "
                 f"{len(result.steps)} steps · {result.elapsed_ms} ms")
    if result.truncated:
        lines += ["", t["truncated"]]
    if result.reply:
        lines += ["", t["summary"], "", result.reply]
    lines += ["", t["steps"]]
    for i, s in enumerate(result.steps, 1):
        mark = "⚠️ " if s.error else ""
        lines.append(f"{i}. {mark}`{s.tool}` · {s.elapsed_ms} ms")
    lines += ["", t["diff"], ""]
    if result.diff.strip():
        lines.append("```diff\n" + result.diff.strip()[:12000] + "\n```")
    else:
        lines.append(t["no_diff"])
    lines += ["", "```", result.final_test_output.strip()[-1500:], "```"]
    return "\n".join(lines)
