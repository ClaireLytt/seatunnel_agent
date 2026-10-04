# -*- coding: utf-8 -*-
"""Optional LLM root-cause advice for the top log clusters.

Strictly additive: the deterministic clustering is never modified.  The
advice renders in its own UI panel / report section, always marked
``llm-generated``.  Callers must skip this module when no API key is
configured.
"""

from __future__ import annotations

from ..config import Settings
from ..llm import LLMClient
from .clusterer import InspectReport

ADVISOR_MARKER = "🤖 llm-generated"

_SYSTEM_PROMPT = """\
You are a senior data-platform SRE. You are given the top exception \
clusters mined from a SeaTunnel / Hadoop-ecosystem log directory. For each \
cluster give: the most likely root cause, how to confirm it, and the fix \
or mitigation. Be specific to the exception and stack frame shown; never \
invent log content that is not present. Answer in {language}, concise \
bullet points per cluster. Start your reply with the marker line \
`{marker}`.
"""


def generate_advice(settings: Settings, report: InspectReport,
                    lang: str = "zh", top: int = 5) -> str:
    """One LLM call for the top clusters; empty string when nothing to do."""
    clusters = report.clusters[:top]
    if not clusters:
        return ""
    blocks = []
    for i, c in enumerate(clusters, start=1):
        blocks.append(
            f"## Cluster {i} (level={c.level}, count={c.count})\n"
            f"exception: {c.exception or '-'}\n"
            f"template: {c.template or '-'}\n"
            f"top frame: {c.top_frame or '-'}\n"
            f"sample:\n```\n{c.sample[:1500]}\n```")
    system = _SYSTEM_PROMPT.format(
        language="English" if lang == "en" else "Chinese",
        marker=ADVISOR_MARKER)
    llm = LLMClient(settings)
    resp = llm.chat(system, [{"role": "user", "content": "\n\n".join(blocks)}])
    text = (resp.reply_text or "").strip()
    if not text:
        return ""
    if not text.startswith(ADVISOR_MARKER):
        text = f"{ADVISOR_MARKER}\n{text}"
    return text
