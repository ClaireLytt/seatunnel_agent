"""Render a DagDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import DagDraft
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(draft: DagDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(dag_id=draft.dag_id,
                                          tasks=len(draft.tasks),
                                          edges=draft.edges,
                                          schedule=draft.schedule,
                                          externals=len(draft.externals)),
             "", f"### {tp(lang, 'rpt_tasks')}"]
    rows = [[f"`{t.task_id}`", f"`{t.table}`",
             ", ".join(f"`{u}`" for u in t.upstream) or "-",
             ", ".join(t.external) or "-"]
            for t in draft.tasks]
    lines += md_table([tp(lang, "col_task"), tp(lang, "col_table"),
                       tp(lang, "col_upstream"),
                       tp(lang, "col_external")], rows)
    lines += ["", f"### {tp(lang, 'rpt_python')}", "```python",
              draft.python_text.rstrip(), "```"]
    if draft.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in draft.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
