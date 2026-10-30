"""Optional LLM advice for a pipeline diagnosis.

Strictly additive: the deterministic diagnosis is never modified. The
advice renders in its own panel / section, always marked ``llm-generated``.
Callers must skip this module when no API key is configured.
"""

from __future__ import annotations

from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.llm import LLMClient

from .diagnoser import Diagnosis

ADVISOR_MARKER = "🤖 llm-generated"

_SYSTEM_PROMPT = """\
You are a senior big-data platform SRE diagnosing one failed pipeline run \
(Spark / Hive / SeaTunnel). You get the deterministic diagnosis: matched \
failure signatures (with cause and fix) and unmatched error clusters. \
Confirm or challenge the primary suspect, explain how the findings relate \
(which failure caused which), diagnose the unmatched clusters, and give a \
step-by-step recovery plan. Be specific to the evidence shown; never invent \
log content that is not present. Answer in {language}, concise bullet \
points. Start your reply with the marker line `{marker}`.
"""


def generate_advice(settings: Settings, diag: Diagnosis,
                    lang: str = "zh", top: int = 5) -> str:
    """One LLM call over the diagnosis; empty string when nothing to do."""
    if not diag.findings and not diag.unmatched:
        return ""
    blocks = [f"engines: {diag.engines or 'unknown'}"]
    for i, f in enumerate(diag.findings[:top], start=1):
        blocks.append(
            f"## Finding {i} [{f.severity}/{f.engine}] {f.title_en}\n"
            f"exception: {f.exception or '-'} ×{f.count}\n"
            f"kb cause: {f.cause_en}\nkb fix: {f.fix_en}\n"
            f"evidence:\n```\n{f.sample[:1200]}\n```")
    for i, c in enumerate(diag.unmatched[:top], start=1):
        blocks.append(
            f"## Unmatched cluster {i} ×{c.count}\n"
            f"exception: {c.exception or '-'}\ntemplate: {c.template or '-'}\n"
            f"sample:\n```\n{c.sample[:1200]}\n```")
    system = _SYSTEM_PROMPT.format(
        language="English" if lang == "en" else "Chinese",
        marker=ADVISOR_MARKER)
    llm = LLMClient(settings, agent="pipeline_doctor")
    resp = llm.chat(system, [{"role": "user", "content": "\n\n".join(blocks)}])
    text = (resp.reply_text or "").strip()
    if not text:
        return ""
    if not text.startswith(ADVISOR_MARKER):
        text = f"{ADVISOR_MARKER}\n{text}"
    return text
