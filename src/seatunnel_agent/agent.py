from __future__ import annotations

import json
import threading
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel

from .config import Settings, env_int
from .context import truncate_messages
from .llm import LLMClient
from .prompts import build_system_prompt
from .tools import TOOL_DEFINITIONS, execute_tool
from .utils import truncate

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
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS)
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
        text_delta_cb = None
        if self._on_event:
            def text_delta_cb(chunk: str) -> None:
                self._emit("text_delta", {"text": chunk})

        self.stop_event.clear()

        for iteration in range(MAX_LOOP_ITERATIONS):
            if self.stop_event.is_set():
                return self._finish_stopped()

            self._emit("step", {
                "iteration": iteration + 1,
                "max": MAX_LOOP_ITERATIONS,
                "phase": "thinking",
            })

            effective_prompt = system_prompt
            context_hint = self._build_context_hint()
            if context_hint:
                effective_prompt = system_prompt + context_hint

            self.messages = truncate_messages(self.messages)
            resp = self.llm.chat(effective_prompt, self.messages, on_text_delta=text_delta_cb)

            self.messages.append(self.llm.append_assistant(resp.raw_content))

            if resp.usage:
                self._emit("usage", resp.usage)

            self._emit_parsed_events(resp)
            self._display_parsed(resp)

            if not resp.wants_tool_use:
                final = resp.reply_text
                self._emit("final_answer", {"text": final})
                return final

            self._emit("step", {
                "iteration": iteration + 1,
                "max": MAX_LOOP_ITERATIONS,
                "phase": "executing_tools",
                "tool_count": len(resp.tool_calls),
            })

            tool_results = []
            stopped_mid_tools = False
            for tc in resp.tool_calls:
                if self.stop_event.is_set():
                    # Keep history valid: every tool_use needs a tool_result.
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps({"error": "Cancelled: stopped by user"}),
                    })
                    stopped_mid_tools = True
                    continue

                self._display_tool_call(tc.name, tc.input)
                self._emit("tool_call", {"name": tc.name, "input": tc.input})

                result = execute_tool(tc.name, tc.input, self.settings)

                self._display_tool_result(tc.name, result)
                self._emit("tool_result", {"name": tc.name, "result": result})

                self._update_context(tc.name, tc.input, result)

                if tc.name == "run_seatunnel_job":
                    self._track_retry(result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result,
                })

            result_msg = self.llm.build_tool_result_message(tool_results)
            if isinstance(result_msg, list):
                self.messages.extend(result_msg)
            else:
                self.messages.append(result_msg)

            if stopped_mid_tools:
                return self._finish_stopped()

            if self.retry_count >= self.settings.max_retries:
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

        msg = "Agent loop reached maximum iterations without completing."
        self._emit("final_answer", {"text": msg})
        return msg

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

    def _emit_parsed_events(self, resp: Any) -> None:
        if resp.thinking_text:
            self._emit("thinking", {"text": resp.thinking_text})
        if resp.reply_text:
            self._emit("text", {"text": resp.reply_text})

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
