"""Render a DagDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import DagDraft
from .i18n import tp

__all__ = ["render_markdown"]


_FENCE = {"airflow": "python", "dolphinscheduler": "json",
          "azkaban": "yaml"}


def render_markdown(draft: DagDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    engine = getattr(draft, "engine", "airflow")
    title_key = ("rpt_title" if engine == "airflow"
                 else f"rpt_title_{engine}")
    lines = [f"## {tp(lang, title_key)}", "",
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
    file_key = ("rpt_python" if engine == "airflow"
                else f"rpt_file_{engine}")
    lines += ["", f"### {tp(lang, file_key)}", f"```{_FENCE[engine]}",
              draft.python_text.rstrip(), "```"]
    if draft.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in draft.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
