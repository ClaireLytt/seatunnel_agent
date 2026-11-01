"""Render a MockResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import MockResult
from .i18n import tp

__all__ = ["render_markdown"]

_PREVIEW = 10


def _strategy_label(plan, lang: str) -> str:
    if plan.strategy.startswith("fake_"):
        return tp(lang, "st_fake").format(category=plan.strategy[5:])
    return tp(lang, "st_" + plan.strategy)


def render_markdown(result: MockResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(count=result.rows_generated,
                                          sample=result.sample_rows,
                                          seed=result.seed), "",
             f"### {tp(lang, 'rpt_plans')}"]
    rows = [[f"`{p.name}`", _strategy_label(p, lang),
             f"`{p.detail}`" if p.detail else "-"]
            for p in result.plans]
    lines += md_table([tp(lang, "col_name"), tp(lang, "col_strategy"),
                       tp(lang, "col_detail")], rows)
    head = result.rows[:_PREVIEW]
    lines += ["", f"### {tp(lang, 'rpt_preview').format(n=len(head))}"]
    body = [[str(r.get(h)) if r.get(h) is not None else ""
             for h in result.headers] for r in head]
    lines += md_table(list(result.headers), body)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
