# -*- coding: utf-8 -*-
"""Markdown rendering for prompt-lab matrices: metrics table, side-by-side
outputs, and a unified diff between two cells."""

from __future__ import annotations

import difflib

from .runner import CellResult, MatrixResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## Prompt Lab",
        "header": "Profile | Provider | Model | In | Out | Latency | Status",
        "ok": "ok",
        "outputs": "### Outputs",
        "diff_title": "### Diff: {a} → {b}",
        "diff_same": "The two replies are identical.",
        "all_failed": "⚠️ Every profile errored — nothing to compare.",
    },
    "zh": {
        "title": "## Prompt 实验室",
        "header": "档案 | 提供商 | 模型 | 输入 | 输出 | 耗时 | 状态",
        "ok": "成功",
        "outputs": "### 各档案输出",
        "diff_title": "### 差异: {a} → {b}",
        "diff_same": "两个回复完全相同。",
        "all_failed": "⚠️ 所有档案都调用失败 — 没有可比较的输出。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)][key]


def render_matrix_markdown(result: MatrixResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [_t(lang, "title"), ""]
    lines.append("| " + _t(lang, "header") + " |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in result.cells:
        status = f"⚠️ {c.error}" if c.error else _t(lang, "ok")
        lines.append(
            f"| `{c.profile}` | {c.provider or '—'} | `{c.model or '—'}` "
            f"| {c.input_tokens:,} | {c.output_tokens:,} "
            f"| {c.latency_ms} ms | {status} |")
    if result.all_failed:
        lines += ["", _t(lang, "all_failed")]
        return "\n".join(lines)
    lines += ["", _t(lang, "outputs")]
    for c in result.cells:
        lines.append("")
        lines.append(f"#### `{c.profile}` · `{c.model}`")
        lines.append(c.error and f"⚠️ {c.error}" or (c.reply or "_(empty)_"))
    return "\n".join(lines)


def render_diff(a: CellResult, b: CellResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    title = _t(lang, "diff_title").format(a=a.profile, b=b.profile)
    diff = list(difflib.unified_diff(
        (a.reply or "").splitlines(), (b.reply or "").splitlines(),
        fromfile=f"{a.profile} ({a.model})", tofile=f"{b.profile} ({b.model})",
        lineterm=""))
    if not diff:
        return f"{title}\n\n{_t(lang, 'diff_same')}"
    return title + "\n\n```diff\n" + "\n".join(diff) + "\n```"
