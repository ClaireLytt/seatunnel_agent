from __future__ import annotations

import json
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Settings
from .llm import LLMClient
from .prompts import build_system_prompt
from .tools import TOOL_DEFINITIONS, execute_tool
from .utils import truncate

MAX_LOOP_ITERATIONS = 20

EventCallback = Callable[[str, dict[str, Any]], None]


class SeaTunnelAgent:
    def __init__(
        self,
        settings: Settings,
        on_event: EventCallback | None = None,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings)
        self.messages: list[dict[str, Any]] = []
        self.retry_count = 0
        self.console = Console()
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
        for iteration in range(MAX_LOOP_ITERATIONS):
            text_delta_cb = None
            if self._on_event:
                def text_delta_cb(chunk: str) -> None:
                    self._emit("text_delta", {"text": chunk})
            resp = self.llm.chat(system_prompt, self.messages, on_text_delta=text_delta_cb)

            self.messages.append(self.llm.append_assistant(resp.raw_content))

            self._emit_parsed_events(resp)
            self._display_parsed(resp)

            if not resp.wants_tool_use:
                final = resp.reply_text
                self._emit("final_answer", {"text": final})
                return final

            tool_results = []
            for tc in resp.tool_calls:
                self._display_tool_call(tc.name, tc.input)
                self._emit("tool_call", {"name": tc.name, "input": tc.input})

                result = execute_tool(tc.name, tc.input, self.settings)

                self._display_tool_result(tc.name, result)
                self._emit("tool_result", {"name": tc.name, "result": result})

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

            if self.retry_count >= self.settings.max_retries:
                self.messages.append({
                    "role": "user",
                    "content": (
                        f"SYSTEM: Maximum retry limit ({self.settings.max_retries}) reached. "
                        "Please summarize what you tried and suggest manual fixes."
                    ),
                })

        msg = "Agent loop reached maximum iterations without completing."
        self._emit("final_answer", {"text": msg})
        return msg

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
                self.console.print(f"  [green]Success[/green]")
            elif data.get("valid") is True:
                self.console.print(f"  [green]Valid config[/green]")
            elif data.get("valid") is False:
                errors = data.get("errors", [])
                self.console.print(f"  [red]Invalid:[/red] {'; '.join(errors)[:200]}")
            else:
                self.console.print(f"  [dim]Result received ({len(result)} chars)[/dim]")
        except (json.JSONDecodeError, AttributeError):
            self.console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
