# -*- coding: utf-8 -*-
"""Eval targets — adapters that turn a case input into one LLM output.

``TARGETS`` maps an agent name to ``fn(case_input, settings, client_factory)
-> {"output": str, "usage": dict, "latency_ms": int}``.  The registry is the
test seam: tests register fakes or inject a fake ``client_factory``.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..config import Settings

AdapterResult = dict[str, Any]
Adapter = Callable[[dict[str, Any], Settings, Callable], AdapterResult]

_DEFAULT_SYSTEM = "You are a helpful assistant."


def _chat(system: str, user: str, settings: Settings,
          client_factory: Callable) -> AdapterResult:
    start = time.time()
    client = client_factory(settings)
    resp = client.chat(system, [{"role": "user", "content": user}])
    return {
        "output": resp.reply_text or "",
        "usage": dict(resp.usage or {}),
        "latency_ms": int((time.time() - start) * 1000),
    }


def run_raw_prompt(inp: dict[str, Any], settings: Settings,
                   client_factory: Callable) -> AdapterResult:
    """input: {prompt, system?}"""
    prompt = str(inp.get("prompt") or "")
    if not prompt.strip():
        raise ValueError("raw_prompt 需要 input.prompt")
    return _chat(str(inp.get("system") or _DEFAULT_SYSTEM), prompt,
                 settings, client_factory)


def run_text2sql(inp: dict[str, Any], settings: Settings,
                 client_factory: Callable) -> AdapterResult:
    """input: {question, ddl?, dialect?} — the production text2sql system
    prompt; table DDL (if any) is appended to the question the same way the
    schema summary would be."""
    question = str(inp.get("question") or "")
    if not question.strip():
        raise ValueError("text2sql 需要 input.question")
    from ..text2sql.prompts import build_text2sql_prompt
    system = build_text2sql_prompt(None, dialect=str(inp.get("dialect",
                                                             "hive")))
    user = question
    if inp.get("ddl"):
        user += "\n\n## Registered Tables (仅允许查询以下表)\n\n" \
                + str(inp["ddl"])
    return _chat(system, user, settings, client_factory)


def run_sql_review(inp: dict[str, Any], settings: Settings,
                   client_factory: Callable) -> AdapterResult:
    """input: {sql, dialect?, lang?} — the production review system prompt."""
    sql = str(inp.get("sql") or "")
    if not sql.strip():
        raise ValueError("sql_review 需要 input.sql")
    from ..sql_review.prompts import build_review_prompt
    system = build_review_prompt(dialect=str(inp.get("dialect", "hive")),
                                 store=None,
                                 lang=str(inp.get("lang", "zh")))
    return _chat(system, sql, settings, client_factory)


TARGETS: dict[str, Adapter] = {
    "raw_prompt": run_raw_prompt,
    "text2sql": run_text2sql,
    "sql_review": run_sql_review,
}
