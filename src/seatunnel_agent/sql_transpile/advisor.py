# -*- coding: utf-8 -*-
"""Optional LLM advice for transpile findings.

Strictly additive: the deterministic result is never modified.  The advice
text is rendered in its own report section / UI panel, always marked
``llm-generated``.  Callers must skip this module entirely under
``--no-llm`` or when no API key is configured.
"""

from __future__ import annotations

from ..config import Settings
from ..llm import LLMClient
from .i18n import issue_message, normalize_lang
from .prompts import ADVISOR_MARKER, ADVISOR_SYSTEM_PROMPT
from .transpiler import TranspileResult

# Only these kinds benefit from an LLM look; info-level syntax notes don't.
_ADVISABLE = {"parse_error", "unsupported", "unknown_function",
              "storage_clause"}


def advisable_issues(result: TranspileResult) -> list:
    return [i for i in result.issues() if i.kind in _ADVISABLE]


def generate_advice(
    settings: Settings, result: TranspileResult, lang: str = "zh"
) -> str:
    """One LLM call for the whole result. Returns markdown starting with
    ``ADVISOR_MARKER``; empty string when nothing needs advice."""
    issues = advisable_issues(result)
    if not issues:
        return ""
    lang = normalize_lang(lang)

    findings = "\n".join(
        f"- [{i.level}] line {i.line}: "
        f"{issue_message(lang, i.kind, i.params)} (`{i.snippet}`)"
        for i in issues
    )
    originals = "\n\n".join(
        f"-- statement {s.index}\n{s.source_sql.strip()}"
        for s in result.statements
        if any(i.kind in _ADVISABLE for i in s.issues)
    )
    translated = "\n\n".join(
        f"-- statement {s.index}\n{s.output_sql.rstrip()}"
        for s in result.statements
        if s.ok and any(i.kind in _ADVISABLE for i in s.issues)
    )

    system = ADVISOR_SYSTEM_PROMPT.format(
        src=result.src_dialect, dst=result.dst_dialect,
        language="English" if lang == "en" else "Chinese",
        marker=ADVISOR_MARKER,
    )
    user = (
        f"Original SQL:\n```sql\n{originals}\n```\n\n"
        f"Deterministic translation:\n```sql\n{translated or '-- (none)'}\n```\n\n"
        f"Findings:\n{findings}\n"
    )
    llm = LLMClient(settings)
    resp = llm.chat(system, [{"role": "user", "content": user}])
    text = (resp.reply_text or "").strip()
    if not text:
        return ""
    if not text.startswith(ADVISOR_MARKER):
        text = f"{ADVISOR_MARKER}\n{text}"
    return text
