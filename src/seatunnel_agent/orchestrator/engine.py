# -*- coding: utf-8 -*-
"""Orchestrator engine — a bounded tool-use loop over the agent catalog.

One ``LLMClient`` chat with one tool per routable agent; the model picks
and chains tools (``LLMClient`` already speaks both the Anthropic and the
OpenAI tool-call dialects).  Tool errors become tool results, never crashes;
at ``max_steps`` the model is forced to summarize what it has.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import Settings
from .catalog import AgentSpec, build_catalog, tool_definitions
from .prompts import build_system_prompt

_MAX_RESULT_CHARS = 20000  # keep one tool's markdown from flooding the context


@dataclass
class Step:
    tool: str
    input: dict[str, Any]
    output: str
    elapsed_ms: int
    error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "input": self.input, "output": self.output,
                "elapsed_ms": self.elapsed_ms, "error": self.error}


@dataclass
class OrchestratorResult:
    reply: str
    steps: list[Step] = field(default_factory=list)
    truncated: bool = False  # hit max_steps
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"reply": self.reply,
                "steps": [s.to_dict() for s in self.steps],
                "truncated": self.truncated, "elapsed_ms": self.elapsed_ms}


class Orchestrator:
    """``client`` is injectable (the test seam); the default is a real
    ``LLMClient`` armed with one tool per catalog entry."""

    def __init__(self,
                 settings: Settings,
                 lang: str = "zh",
                 max_steps: int = 5,
                 client: Any = None,
                 catalog: dict[str, AgentSpec] | None = None) -> None:
        self.settings = settings
        self.lang = "en" if (lang or "").lower().startswith("en") else "zh"
        self.max_steps = max(1, max_steps)
        self.catalog = catalog if catalog is not None else build_catalog(
            default_lang=self.lang)
        if client is None:
            from ..llm import LLMClient
            client = LLMClient(settings,
                               tools=tool_definitions(self.catalog),
                               agent="orchestrator")
        self.client = client
        self.system_prompt = build_system_prompt(self.catalog, self.lang)
        self.messages: list[dict[str, Any]] = []

    # ── public API ──────────────────────────────────────────────────────

    def run(self, request: str,
            on_step: Callable[[Step], None] | None = None,
            ) -> OrchestratorResult:
        """Handle one user request (the instance keeps multi-turn history)."""
        if not (request or "").strip():
            raise ValueError("request is required")
        start = time.time()
        self.messages.append({"role": "user", "content": request})
        result = OrchestratorResult(reply="")

        for _turn in range(self.max_steps):
            resp = self.client.chat(self.system_prompt, self.messages)
            self.messages.append(self.client.append_assistant(
                resp.raw_content))
            if not resp.wants_tool_use:
                result.reply = resp.reply_text or ""
                break
            tool_results = []
            for tc in resp.tool_calls:
                step = self._execute(tc.name, tc.input or {})
                result.steps.append(step)
                if on_step:
                    on_step(step)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": step.output,
                })
            result_msg = self.client.build_tool_result_message(tool_results)
            if isinstance(result_msg, list):
                self.messages.extend(result_msg)
            else:
                self.messages.append(result_msg)
        else:
            # Out of turns while the model still wants tools: one forced
            # summary turn with no further tool use.
            result.truncated = True
            self.messages.append({
                "role": "user",
                "content": ("SYSTEM: step limit reached — summarize the "
                            "tool results you already have and answer now, "
                            "without further tool calls."),
            })
            resp = self.client.chat(self.system_prompt, self.messages)
            self.messages.append(self.client.append_assistant(
                resp.raw_content))
            if resp.wants_tool_use:
                # The model ignored the stop order: every tool_use in the
                # history still needs a tool_result, or the NEXT turn of this
                # multi-turn session is rejected by the provider (400).
                cancelled = [{
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": "cancelled: step limit reached",
                } for tc in resp.tool_calls]
                result_msg = self.client.build_tool_result_message(cancelled)
                if isinstance(result_msg, list):
                    self.messages.extend(result_msg)
                else:
                    self.messages.append(result_msg)
            result.reply = resp.reply_text or (
                "已达步数上限,基于已有结果无法继续;请精简需求后重试。"
                if self.lang == "zh" else
                "Step limit reached — please narrow the request and retry.")

        result.elapsed_ms = int((time.time() - start) * 1000)
        return result

    # ── internals ───────────────────────────────────────────────────────

    def _execute(self, name: str, tool_input: dict[str, Any]) -> Step:
        start = time.time()
        spec = self.catalog.get(name)
        if spec is None:
            return Step(tool=name, input=tool_input,
                        output=f"未知工具 / unknown tool: {name}",
                        elapsed_ms=0, error=True)
        try:
            if not isinstance(tool_input, dict):
                tool_input = json.loads(str(tool_input))
            output = str(spec.run(**tool_input))
            error = False
        except Exception as exc:  # noqa: BLE001 — errors go back to the model
            output = f"工具执行失败 / tool failed: {type(exc).__name__}: {exc}"
            error = True
        if len(output) > _MAX_RESULT_CHARS:
            output = output[:_MAX_RESULT_CHARS] + "\n…(truncated)"
        return Step(tool=name, input=tool_input, output=output,
                    elapsed_ms=int((time.time() - start) * 1000), error=error)
