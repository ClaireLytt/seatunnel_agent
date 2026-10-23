"""Orchestrator engine — a bounded tool-use loop over the agent catalog.

The loop body is the shared ``ToolLoopAgent`` (agent_core) — the orchestrator
was its original, now converged back onto it.  This module keeps only what is
orchestrator-specific: the catalog→ToolSpec mapping, transcript seeding, and
the localized step-limit fallback.  ``Step``/``OrchestratorResult`` are the
shared loop-telemetry types, re-exported for the api/report modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from seatunnel_agent.agent_core import LoopResult, Step, ToolLoopAgent, ToolSpec
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.utils import normalize_lang

from .catalog import AgentSpec, build_catalog, tool_definitions
from .prompts import build_system_prompt

OrchestratorResult = LoopResult

__all__ = ["Orchestrator", "OrchestratorResult", "Step"]


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
        self.lang = normalize_lang(lang)
        self.max_steps = max(1, max_steps)
        self.catalog = catalog if catalog is not None else build_catalog(
            default_lang=self.lang)
        if client is None:
            from seatunnel_agent.common.llm import LLMClient
            client = LLMClient(settings,
                               tools=tool_definitions(self.catalog),
                               agent="orchestrator")
        self.client = client
        self.system_prompt = build_system_prompt(self.catalog, self.lang)
        self._loop = ToolLoopAgent(
            settings,
            tools=[ToolSpec(name=s.name, description=s.description,
                            input_schema=s.input_schema, run=s.run)
                   for s in self.catalog.values()],
            system_prompt=self.system_prompt,
            agent_name="orchestrator",
            max_steps=self.max_steps,
            client=client,
        )
        import uuid
        self.session_id = uuid.uuid4().hex[:12]

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._loop.messages

    @messages.setter
    def messages(self, value: list[dict[str, Any]]) -> None:
        self._loop.messages = value

    def seed_transcript(self, turns: list[tuple[str, str]]) -> None:
        """Rebuild context from a persisted plain-text transcript
        (``[(role, text), …]``).  Consecutive same-role texts are merged so
        the history stays strictly alternating (Anthropic requires it);
        tool messages are not restored — the final replies carry what the
        model needs to stay coherent."""
        merged: list[dict[str, Any]] = []
        for role, text in turns:
            if role not in ("user", "assistant") or not (text or "").strip():
                continue
            if merged and merged[-1]["role"] == role:
                merged[-1]["content"] += "\n\n" + text
            else:
                merged.append({"role": role, "content": text})
        if merged and merged[-1]["role"] == "user":
            merged.pop()  # history must end on an assistant turn
        self.messages = merged

    def run(self, request: str,
            on_step: Callable[[Step], None] | None = None,
            ) -> OrchestratorResult:
        """Handle one user request (the instance keeps multi-turn history)."""
        result = self._loop.run(request, on_step=on_step)
        if result.truncated and result.reply == "step limit reached":
            # keep the legacy localized fallback for the empty-summary edge
            result.reply = (
                "已达步数上限,基于已有结果无法继续;请精简需求后重试。"
                if self.lang == "zh" else
                "Step limit reached — please narrow the request and retry.")
        return result
