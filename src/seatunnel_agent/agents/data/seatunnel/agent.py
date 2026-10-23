from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.panel import Panel

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.agent_core.events import legacy_event_adapter
from seatunnel_agent.agents.data.seatunnel.prompts import build_system_prompt
from seatunnel_agent.agents.data.seatunnel.tools import TOOL_DEFINITIONS, execute_tool
from seatunnel_agent.common.config import Settings, env_int
from seatunnel_agent.common.context import truncate_messages
from seatunnel_agent.common.llm import LLMClient
from seatunnel_agent.common.utils import truncate

MAX_LOOP_ITERATIONS = env_int("AGENT_MAX_ITERATIONS", 20)

STOPPED_MESSAGE = "Agent stopped by user."

EventCallback = Callable[[str, dict[str, Any]], None]


class SeaTunnelAgent:
    def __init__(
        self,
        settings: Settings,
        on_event: EventCallback | None = None,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS, agent="seatunnel")
        self.messages: list[dict[str, Any]] = []
        self.retry_count = 0
        self.console = Console()
        self._on_event = on_event
        self.stop_event = threading.Event()
        self.context: dict[str, Any] = {
            "last_config_path": None,
            "last_job_success": None,
            "last_job_error": None,
            "created_configs": [],
            "validated_configs": [],
            "last_doc_lookup": None,
            "last_job_metrics": None,
            "last_batch_result": None,
        }

    def set_event_callback(self, on_event: EventCallback | None) -> None:
        """Attach or detach the UI event callback between turns (REST API use)."""
        self._on_event = on_event

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(event_type, data)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def chat(self, message: str) -> str:
        """Continue a multi-turn conversation, preserving history."""
        system = build_system_prompt("run", self.settings.max_retries)
        self.messages.append({"role": "user", "content": message})
        self.console.print(Panel(message, title="Chat", border_style="cyan"))
        return self._agent_loop(system)

    def run(self, task: str) -> str:
        system = build_system_prompt("run", self.settings.max_retries)
        self.messages = [{"role": "user", "content": task}]
        self.console.print(
            Panel(task, title="Task", border_style="cyan")
        )
        return self._agent_loop(system)

    def run_with_config(self, config_path: str) -> str:
        system = build_system_prompt("run_config", self.settings.max_retries)
        user_msg = (
            f"Run the SeaTunnel job at {config_path}. "
            "If it fails, diagnose the error and fix the config."
        )
        self.messages = [{"role": "user", "content": user_msg}]
        self.console.print(
            Panel(f"Running config: {config_path}", title="Task", border_style="cyan")
        )
        return self._agent_loop(system)

    def validate_only(self, config_path: str) -> str:
        system = build_system_prompt("validate", self.settings.max_retries)
        user_msg = (
            f"Validate the SeaTunnel config at {config_path}. "
            "Report any syntax errors, missing required sections, or potential issues. "
            "Do not run the job."
        )
        self.messages = [{"role": "user", "content": user_msg}]
        self.console.print(
            Panel(f"Validating: {config_path}", title="Task", border_style="cyan")
        )
        return self._agent_loop(system)

    def diagnose_log(self, log_path: str) -> str:
        system = build_system_prompt("diagnose", self.settings.max_retries)
        user_msg = (
            f"Analyze the SeaTunnel log at {log_path}. "
            "Identify the root cause of any errors and suggest fixes."
        )
        self.messages = [{"role": "user", "content": user_msg}]
        self.console.print(
            Panel(f"Diagnosing: {log_path}", title="Task", border_style="cyan")
        )
        return self._agent_loop(system)

    # ------------------------------------------------------------------
    # Core ReAct loop
    # ------------------------------------------------------------------

    def _agent_loop(self, system_prompt: str) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        Agent specifics ride the loop's seams: stop_event, text deltas and
        usage via on_event, the session context hint via system_hint, and
        truncate_messages via the truncation policy. Tool wrappers keep
        context tracking and job-retry accounting; when the retry limit is
        hit the wrapper raises the stop signal and the summary turn runs
        here (legacy semantics). The legacy per-iteration "step"
        (iteration/phase) events are not re-emitted - no consumer existed.
        """
        from types import SimpleNamespace

        def display_turn(thinking: str, text: str) -> None:
            self._display_parsed(SimpleNamespace(thinking_text=thinking,
                                                 reply_text=text))

        adapter = legacy_event_adapter(
            self._emit,
            display_turn=display_turn,
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result)

        self._retry_exhausted = False

        def make_run(name: str):
            def run(**kw: Any) -> str:
                result = execute_tool(name, kw, self.settings)
                self._update_context(name, kw, result)
                if name == "run_seatunnel_job":
                    self._track_retry(result)
                    if self.retry_count >= self.settings.max_retries:
                        self._retry_exhausted = True
                        self.stop_event.set()
                return result
            return run

        tools = [ToolSpec(name=d["name"], description="", input_schema={},
                          run=make_run(d["name"]))
                 for d in TOOL_DEFINITIONS]

        self.stop_event.clear()
        loop = ToolLoopAgent(
            self.settings, tools, system_prompt, "seatunnel",
            max_steps=MAX_LOOP_ITERATIONS, client=self.llm,
            on_event=adapter,  # always: it also drives the Rich CLI display
            stop_event=self.stop_event,
            system_hint=self._build_context_hint,
            truncate=truncate_messages,
            on_limit=lambda: ("Agent loop reached maximum iterations "
                              "without completing."))
        request = self.messages[-1]["content"]
        loop.messages = self.messages[:-1]
        result = loop.run(request)
        self.messages = loop.messages

        if result.stopped and self._retry_exhausted:
            # legacy retry-limit semantics: one forced summary turn
            self.messages.append({
                "role": "user",
                "content": (
                    f"SYSTEM: Maximum retry limit ({self.settings.max_retries}) reached. "
                    "Please summarize what you tried and suggest manual fixes."
                ),
            })
            resp = self.llm.chat(system_prompt, self.messages)
            self.messages.append(self.llm.append_assistant(resp.raw_content))
            final = resp.reply_text or "Maximum retry limit reached."
            self._emit("final_answer", {"text": final})
            return final
        if result.stopped:
            return self._finish_stopped()
        self._emit("final_answer", {"text": result.reply})
        return result.reply

    def _finish_stopped(self) -> str:
        self._emit("final_answer", {"text": STOPPED_MESSAGE})
        return STOPPED_MESSAGE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_context(self, tool_name: str, tool_input: dict[str, Any], result: str) -> None:
        try:
            data = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return

        if tool_name in ("write_config", "use_template") and data.get("success"):
            path = data.get("config_path") or tool_input.get("config_path")
            if path:
                self.context["last_config_path"] = path
                if path not in self.context["created_configs"]:
                    self.context["created_configs"].append(path)
        elif tool_name == "read_config" and data.get("content"):
            self.context["last_config_path"] = tool_input.get("config_path")
        elif tool_name == "run_seatunnel_job":
            self.context["last_job_success"] = data.get("success")
            if not data.get("success"):
                self.context["last_job_error"] = (
                    data.get("error") or data.get("stderr", "")[:200]
                )
            else:
                self.context["last_job_error"] = None
            if data.get("metrics"):
                self.context["last_job_metrics"] = data["metrics"]
        elif tool_name == "validate_config":
            path = tool_input.get("config_path")
            if path and path not in self.context["validated_configs"]:
                self.context["validated_configs"].append(path)
        elif tool_name == "test_connection":
            host = tool_input.get("host", "")
            port = tool_input.get("port", "")
            reachable = data.get("reachable", False)
            self.context["last_connection_test"] = (
                f"{host}:{port} → {'reachable' if reachable else 'unreachable'}"
            )
        elif tool_name == "query_connector_docs":
            self.context["last_doc_lookup"] = tool_input.get("connector_name")
        elif tool_name == "restore_config_version":
            path = tool_input.get("config_path")
            if path:
                self.context["last_config_path"] = path
        elif tool_name == "delete_config" and data.get("success"):
            deleted = data.get("deleted") or tool_input.get("config_path")
            if deleted and deleted in self.context["created_configs"]:
                self.context["created_configs"].remove(deleted)
        elif tool_name == "run_batch":
            self.context["last_batch_result"] = {
                "total": data.get("total"),
                "passed": data.get("passed"),
                "failed": data.get("failed"),
            }

    def _build_context_hint(self) -> str:
        lines: list[str] = []
        ctx = self.context
        if ctx.get("last_config_path"):
            lines.append(f"- **Last config path**: `{ctx['last_config_path']}`")
        else:
            lines.append("- **No config files have been created or read yet in this session.**")
        if ctx.get("last_job_success") is not None:
            status = "Success" if ctx["last_job_success"] else "Failed"
            err = f" — {ctx['last_job_error']}" if ctx.get("last_job_error") else ""
            lines.append(f"- **Last job result**: {status}{err}")
        if ctx.get("created_configs"):
            paths = ", ".join(f"`{p}`" for p in ctx["created_configs"])
            lines.append(f"- **Configs created this session**: {paths}")
        if ctx.get("validated_configs"):
            paths = ", ".join(f"`{p}`" for p in ctx["validated_configs"])
            lines.append(f"- **Validated configs**: {paths}")
        if ctx.get("last_connection_test"):
            lines.append(f"- **Last connection test**: {ctx['last_connection_test']}")
        if ctx.get("last_doc_lookup"):
            lines.append(f"- **Last doc lookup**: `{ctx['last_doc_lookup']}`")
        if ctx.get("last_job_metrics"):
            m = ctx["last_job_metrics"]
            parts = []
            if "total_read_count" in m:
                parts.append(f"Read: {m['total_read_count']} rows")
            if "total_write_count" in m:
                parts.append(f"Written: {m['total_write_count']} rows")
            if "duration_ms" in m:
                parts.append(f"Duration: {m['duration_ms']}ms")
            if parts:
                lines.append(f"- **Last job metrics**: {', '.join(parts)}")
        if ctx.get("last_batch_result"):
            b = ctx["last_batch_result"]
            lines.append(f"- **Last batch run**: {b['passed']}/{b['total']} passed, {b['failed']} failed")
        return (
            "\n\n## Session Context\n\n"
            "Use this information to resolve user references like "
            "\"刚才的配置\", \"the config\", \"run it again\", etc. "
            "Do NOT guess file paths — only use paths listed here or ask the user.\n\n"
            + "\n".join(lines) + "\n"
        )

    def _track_retry(self, result: str) -> None:
        try:
            data = json.loads(result)
            if data.get("success"):
                self.retry_count = 0
            else:
                self.retry_count += 1
                self.console.print(
                    f"  [yellow]Retry {self.retry_count}/{self.settings.max_retries}[/yellow]"
                )
        except (json.JSONDecodeError, AttributeError):
            self.retry_count += 1

    # ------------------------------------------------------------------
    # Display (Rich)
    # ------------------------------------------------------------------

    def _display_parsed(self, resp: Any) -> None:
        if resp.thinking_text:
            self.console.print(
                Panel(
                    truncate(resp.thinking_text, 500),
                    title="Thinking",
                    border_style="dim",
                    style="italic dim",
                )
            )
        if resp.reply_text:
            self.console.print(f"\n{resp.reply_text}")

    def _display_tool_call(self, name: str, inputs: dict[str, Any]) -> None:
        style_map = {
            "run_seatunnel_job": "green",
            "write_config": "yellow",
            "read_config": "blue",
            "read_log": "blue",
            "validate_config": "blue",
            "list_connectors": "blue",
            "test_connection": "cyan",
            "list_templates": "blue",
            "use_template": "yellow",
            "query_connector_docs": "blue",
            "list_config_versions": "blue",
            "run_batch": "green",
            "restore_config_version": "yellow",
            "delete_config": "red",
            "compare_config_versions": "blue",
            "explain_config": "blue",
        }
        color = style_map.get(name, "white")
        args_str = ", ".join(
            f"{k}={repr(v)[:60]}" for k, v in inputs.items() if k != "content"
        )
        self.console.print(
            Panel(
                args_str or "(no arguments)",
                title=f"Calling: {name}",
                border_style=color,
            )
        )

    def _display_tool_result(self, name: str, result: str) -> None:
        try:
            data = json.loads(result)
            if data.get("error"):
                self.console.print(f"  [red]Error:[/red] {data['error'][:200]}")
            elif data.get("success") is True:
                self.console.print("  [green]Success[/green]")
            elif data.get("valid") is True:
                self.console.print("  [green]Valid config[/green]")
            elif data.get("valid") is False:
                errors = data.get("errors", [])
                self.console.print(f"  [red]Invalid:[/red] {'; '.join(errors)[:200]}")
            else:
                self.console.print(f"  [dim]Result received ({len(result)} chars)[/dim]")
        except (json.JSONDecodeError, AttributeError):
            self.console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
