"""Generic bounded tool-use loop — the skeleton every true agent shares.

Generalized from the orchestrator engine: an LLM with a custom tool set and
system prompt acts, observes each tool result, and iterates until it answers
in plain text or hits ``max_steps`` (then one forced summary turn).  Tool
errors become tool results — the loop never crashes on a bad call — and the
``client`` is injectable so every agent built on this tests offline with a
scripted fake.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..common.config import Settings

_MAX_RESULT_CHARS = 20000

# on_event callback: (event_type, payload). Emitted types: "step" (a Step
# dict), "text_delta" ({"text": chunk}), "usage" (the provider usage dict).
EventCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[..., str]


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
class LoopResult:
    reply: str
    steps: list[Step] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: int = 0
    stopped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"reply": self.reply,
                "steps": [s.to_dict() for s in self.steps],
                "truncated": self.truncated, "elapsed_ms": self.elapsed_ms,
                "stopped": self.stopped}


class ToolLoopAgent:
    """``client`` is injectable (the test seam); the default is a real
    ``LLMClient`` armed with the given tools and *agent* attribution."""

    def __init__(self,
                 settings: Settings,
                 tools: list[ToolSpec],
                 system_prompt: str,
                 agent_name: str,
                 max_steps: int = 10,
                 client: Any = None,
                 on_event: EventCallback | None = None,
                 stop_event: threading.Event | None = None,
                 system_hint: Callable[[], str] | None = None,
                 truncate: Callable[[list[dict[str, Any]]],
                                    list[dict[str, Any]]] | None = None,
                 ) -> None:
        self.settings = settings
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.max_steps = max(1, max_steps)
        self.on_event = on_event
        self.stop_event = stop_event if stop_event is not None \
            else threading.Event()
        self.system_hint = system_hint
        self.truncate = truncate
        if client is None:
            from ..common.llm import LLMClient
            client = LLMClient(settings, agent=agent_name, tools=[{
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            } for t in tools])
        self.client = client
        self.messages: list[dict[str, Any]] = []

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self.on_event:
            self.on_event(event_type, data)

    def _chat(self) -> Any:
        """One client turn: hint, truncation, delta streaming, usage event."""
        system = self.system_prompt
        if self.system_hint:
            hint = self.system_hint()
            if hint:
                system = system + hint
        if self.truncate:
            self.messages = self.truncate(self.messages)
        if self.on_event:
            def on_text_delta(chunk: str) -> None:
                self._emit("text_delta", {"text": chunk})
            resp = self.client.chat(system, self.messages,
                                    on_text_delta=on_text_delta)
        else:
            resp = self.client.chat(system, self.messages)
        self.messages.append(self.client.append_assistant(resp.raw_content))
        if getattr(resp, "usage", None):
            self._emit("usage", dict(resp.usage))
        return resp

    def run(self, request: str,
            on_step: Callable[[Step], None] | None = None) -> LoopResult:
        if not (request or "").strip():
            raise ValueError("request is required")
        start = time.time()
        self.messages.append({"role": "user", "content": request})
        result = LoopResult(reply="")

        for _turn in range(self.max_steps):
            if self.stop_event.is_set():
                result.stopped = True
                result.reply = result.reply or "stopped by user"
                break
            resp = self._chat()
            if not resp.wants_tool_use:
                result.reply = resp.reply_text or ""
                break
            tool_results = []
            for tc in resp.tool_calls:
                if self.stop_event.is_set():
                    # keep history valid: every tool_use needs a tool_result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": "cancelled: stopped by user",
                    })
                    result.stopped = True
                    continue
                step = self._execute(tc.name, tc.input or {})
                result.steps.append(step)
                if on_step:
                    on_step(step)
                self._emit("step", step.to_dict())
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": step.output,
                })
            self._append_results(tool_results)
            if result.stopped:
                result.reply = "stopped by user"
                break
        else:
            result.truncated = True
            self.messages.append({
                "role": "user",
                "content": ("SYSTEM: step limit reached — summarize what "
                            "you have and answer now, without further tool "
                            "calls."),
            })
            resp = self._chat()
            if resp.wants_tool_use:
                # answer every dangling tool_use or the next turn 400s
                cancelled = [{"type": "tool_result", "tool_use_id": tc.id,
                              "content": "cancelled: step limit reached"}
                             for tc in resp.tool_calls]
                self._append_results(cancelled)
            result.reply = resp.reply_text or "step limit reached"

        result.elapsed_ms = int((time.time() - start) * 1000)
        return result

    def _append_results(self, tool_results: list[dict[str, Any]]) -> None:
        msg = self.client.build_tool_result_message(tool_results)
        if isinstance(msg, list):
            self.messages.extend(msg)
        else:
            self.messages.append(msg)

    def _execute(self, name: str, tool_input: dict[str, Any]) -> Step:
        start = time.time()
        spec = self.tools.get(name)
        if spec is None:
            return Step(tool=name, input=tool_input,
                        output=f"unknown tool: {name}", elapsed_ms=0,
                        error=True)
        try:
            if not isinstance(tool_input, dict):
                tool_input = json.loads(str(tool_input))
            output = str(spec.run(**tool_input))
            error = False
        except Exception as exc:
            output = f"tool failed: {type(exc).__name__}: {exc}"
            error = True
        if len(output) > _MAX_RESULT_CHARS:
            output = output[:_MAX_RESULT_CHARS] + "\n…(truncated)"
        return Step(tool=name, input=tool_input, output=output,
                    elapsed_ms=int((time.time() - start) * 1000), error=error)
