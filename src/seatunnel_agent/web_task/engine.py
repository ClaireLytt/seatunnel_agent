# -*- coding: utf-8 -*-
"""Web-task agent — goal + URL → observe/act loop over a real browser.

A light computer-use loop: snapshot (indexed interactive elements) → the
LLM picks click/fill/goto → observe again.  The session is injectable, so
the whole loop tests offline against a fake page; navigation is confined to
the start URL's origin unless explicitly allowed."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..agent_core import Step, ToolLoopAgent, ToolSpec
from ..config import Settings

_SYSTEM = """\
You are a web-task agent driving a real browser.

Loop: call snapshot to see the page (interactive elements are numbered),
then act with click/fill/goto — after every action, snapshot again before
deciding. Element indexes are only valid for the LATEST snapshot.

Rules:
- Never invent indexes; if unsure, snapshot.
- Stay on task; do not wander to unrelated pages.
- When the goal is achieved, reply "DONE: <what you did / what you saw>".
- If it cannot be achieved, reply "FAILED: <why>".
Answer in the user's language.
"""


def _build_tools(session: Any) -> list[ToolSpec]:
    s = {"type": "string"}
    n = {"type": "integer"}
    return [
        ToolSpec("snapshot", "当前页面快照:URL、标题与编号的可交互元素。",
                 {"type": "object", "properties": {}, "required": []},
                 session.snapshot),
        ToolSpec("click", "点击快照里编号为 index 的元素。",
                 {"type": "object", "properties": {"index": n},
                  "required": ["index"]}, session.click),
        ToolSpec("fill", "向编号为 index 的输入框填入 text(覆盖原值)。",
                 {"type": "object",
                  "properties": {"index": n, "text": s},
                  "required": ["index", "text"]}, session.fill),
        ToolSpec("goto", "跳转到 url(默认仅限起始同源)。",
                 {"type": "object", "properties": {"url": s},
                  "required": ["url"]}, session.goto),
    ]


@dataclass
class WebTaskResult:
    success: bool
    reply: str
    steps: list[Step] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "reply": self.reply,
                "steps": [s.to_dict() for s in self.steps],
                "truncated": self.truncated, "elapsed_ms": self.elapsed_ms}


def run_task(goal: str, url: str, settings: Settings,
             session: Any = None, client: Any = None,
             max_steps: int = 15, allow_external: bool = False,
             headed: bool = False, on_step=None) -> WebTaskResult:
    start = time.time()
    own_session = session is None
    if own_session:
        from .session import PlaywrightSession
        session = PlaywrightSession(allow_external=allow_external,
                                    headed=headed)
        try:
            session.start(url)
        except Exception:
            # launch can fail after the driver process started (browsers
            # not installed is the classic) — never leak it
            session.close()
            raise
    try:
        agent = ToolLoopAgent(settings, tools=_build_tools(session),
                              system_prompt=_SYSTEM, agent_name="web_task",
                              max_steps=max_steps, client=client)
        loop = agent.run(f"GOAL: {goal}\nSTART URL: {url}", on_step=on_step)
        return WebTaskResult(
            success=loop.reply.strip().upper().startswith("DONE"),
            reply=loop.reply, steps=loop.steps, truncated=loop.truncated,
            elapsed_ms=int((time.time() - start) * 1000))
    finally:
        if own_session:
            session.close()
