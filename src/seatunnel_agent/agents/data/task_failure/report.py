"""Render a FailureResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .classifier import FailureResult
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_CLUSTERS = 12


def render_markdown(result: FailureResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    causes = " · ".join(f"{tp(lang, 'cause_' + c)}×{n}"
                        for c, n in result.causes.items())
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(total=result.total,
                                          causes=causes), "",
             f"### {tp(lang, 'rpt_clusters')}"]
    rows = []
    for c in result.clusters[:_TOP_CLUSTERS]:
        members = ", ".join(f"`{t}`" for t in c.tasks[:4])
        if len(c.tasks) > 4:
            members += f" +{len(c.tasks) - 4}"
        rows.append([tp(lang, "cause_" + c.cause), str(len(c.tasks)),
                     members, tp(lang, "retry_" + c.retry_verdict),
                     f"`{c.sample_error[:80]}`"])
    lines += md_table([tp(lang, "col_cause"), tp(lang, "col_count"),
                       tp(lang, "col_members"), tp(lang, "col_retry"),
                       tp(lang, "col_sample")], rows)
    lines += ["", f"### {tp(lang, 'rpt_rx')}"]
    lines += [tp(lang, "rx_" + c) for c in result.causes]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
