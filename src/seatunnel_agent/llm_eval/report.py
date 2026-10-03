# -*- coding: utf-8 -*-
"""Bilingual markdown report for eval runs."""

from __future__ import annotations

from typing import Any

from .runner import SuiteResult


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## LLM Eval · {suite}",
        "summary": ("Score **{score:.0%}** · {passed}/{total} cases passed "
                    "· {elapsed} ms"),
        "header": "Case | Agent | Score | Tokens | Latency | Status",
        "ok": "✅ pass",
        "fail": "❌ fail",
        "error": "⚠️ error",
        "failed_title": "### Failed checks",
        "advisory": " (judge, advisory)",
        "baseline_none": "> No previous run of this suite — baseline recorded.",
        "baseline_ok": "> No regression vs the previous run.",
        "baseline_bad": ("> ⚠️ **Regression** vs the previous run: "
                         "{cases} flipped pass→fail, score drop {drop:+.2%}."),
    },
    "zh": {
        "title": "## LLM 评测 · {suite}",
        "summary": ("得分 **{score:.0%}** · 通过 {passed}/{total} 个 case "
                    "· {elapsed} ms"),
        "header": "Case | Agent | 得分 | Tokens | 耗时 | 状态",
        "ok": "✅ 通过",
        "fail": "❌ 未过",
        "error": "⚠️ 出错",
        "failed_title": "### 未通过的检查",
        "advisory": "(judge,仅参考)",
        "baseline_none": "> 该套件没有历史运行 — 本次已记录为基线。",
        "baseline_ok": "> 相比上次运行没有回归。",
        "baseline_bad": ("> ⚠️ 相比上次运行**存在回归**:{cases} 由过变挂,"
                         "总分变化 {drop:+.2%}。"),
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)][key]


def render_markdown(result: SuiteResult, lang: str = "zh",
                    regression: dict[str, Any] | None = None) -> str:
    lang = normalize_lang(lang)
    passed = sum(1 for c in result.cases if c.passed)
    lines = [_t(lang, "title").format(suite=result.suite), ""]
    lines.append(_t(lang, "summary").format(
        score=result.score, passed=passed, total=len(result.cases),
        elapsed=result.elapsed_ms))
    if regression is not None:
        lines.append("")
        if not regression["has_baseline"]:
            lines.append(_t(lang, "baseline_none"))
        elif regression["regressed"]:
            lines.append(_t(lang, "baseline_bad").format(
                cases=", ".join(f"`{c}`" for c in
                                regression["regressed_cases"]) or "—",
                drop=-regression["score_drop"]))
        else:
            lines.append(_t(lang, "baseline_ok"))
    lines += ["", "| " + _t(lang, "header") + " |",
              "|---|---|---|---|---|---|"]
    for c in result.cases:
        status = (_t(lang, "error") if c.error
                  else _t(lang, "ok") if c.passed else _t(lang, "fail"))
        tokens = (c.usage.get("input_tokens", 0)
                  + c.usage.get("output_tokens", 0))
        lines.append(f"| `{c.id}` | {c.agent} | {c.score:.0%} | {tokens:,} "
                     f"| {c.latency_ms} ms | {status} |")

    details: list[str] = []
    for c in result.cases:
        if c.error:
            details.append(f"- `{c.id}`: {c.error}")
            continue
        for chk in c.checks:
            if chk.passed:
                continue
            adv = _t(lang, "advisory") if chk.advisory else ""
            details.append(f"- `{c.id}` · {chk.type}{adv}: {chk.detail}")
    if details:
        lines += ["", _t(lang, "failed_title")] + details
    return "\n".join(lines)
