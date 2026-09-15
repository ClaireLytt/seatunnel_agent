"""Text2SQL (Chat BI) agent: natural language -> SQL -> results/CSV.

Supports multiple datasources (Hive, MySQL, SQL Server, Spark SQL, Flink SQL,
ClickHouse, Doris, PostgreSQL).
Mirrors SeaTunnelAgent's ReAct loop and event protocol so the existing UI
streaming machinery (EventCollector) works unchanged.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel

from ..config import Settings
from ..context import truncate_messages
from ..llm import LLMClient
from ..utils import truncate
from .executor import DatabaseConfig
from .prompts import build_text2sql_prompt
from .schema import SchemaStore
from .tools import TOOL_DEFINITIONS, Text2SQLRuntime, execute_text2sql_tool

MAX_LOOP_ITERATIONS = 15

EventCallback = Callable[[str, dict[str, Any]], None]


class Text2SQLAgent:
    def __init__(
        self,
        settings: Settings,
        store: SchemaStore,
        ds_type: str = "hive",
        db_config: DatabaseConfig | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS)
        self.runtime = Text2SQLRuntime(store=store, ds_type=ds_type, db_config=db_config)
        self.messages: list[dict[str, Any]] = []
        self.console = Console()
        self._on_event = on_event
        self._system_prompt = build_text2sql_prompt(store, dialect=ds_type)

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(event_type, data)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def chat(self, message: str) -> str:
        """Continue a multi-turn conversation, preserving history."""
        self.messages.append({"role": "user", "content": message})
        self.console.print(Panel(message, title="Text2SQL", border_style="cyan"))
        return self._agent_loop()

    def run(self, question: str) -> str:
        """Answer a single question with fresh history."""
        self.messages = [{"role": "user", "content": question}]
        self.console.print(Panel(question, title="Text2SQL", border_style="cyan"))
        return self._agent_loop()

    def reset(self) -> None:
        self.messages = []
        self.runtime.last_result = None
        self.runtime.last_sql = ""
        self.runtime.sql_retries = 0

    # ------------------------------------------------------------------
    # Core ReAct loop
    # ------------------------------------------------------------------

    def _agent_loop(self) -> str:
        text_delta_cb = None
        if self._on_event:
            def text_delta_cb(chunk: str) -> None:
                self._emit("text_delta", {"text": chunk})

        for iteration in range(MAX_LOOP_ITERATIONS):
            self._emit("step", {
                "iteration": iteration + 1,
                "max": MAX_LOOP_ITERATIONS,
                "phase": "thinking",
            })

            self.messages = truncate_messages(self.messages)
            resp = self.llm.chat(
                self._system_prompt, self.messages, on_text_delta=text_delta_cb
            )

            self.messages.append(self.llm.append_assistant(resp.raw_content))

            if resp.usage:
                self._emit("usage", resp.usage)

            if resp.thinking_text:
                self._emit("thinking", {"text": resp.thinking_text})
                self.console.print(
                    Panel(
                        truncate(resp.thinking_text, 500),
                        title="Thinking",
                        border_style="dim",
                        style="italic dim",
                    )
                )
            if resp.reply_text:
                self._emit("text", {"text": resp.reply_text})
                self.console.print(f"\n{resp.reply_text}")

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
            for tc in resp.tool_calls:
                self._display_tool_call(tc.name, tc.input)
                self._emit("tool_call", {"name": tc.name, "input": tc.input})

                result = execute_text2sql_tool(tc.name, tc.input, self.runtime)

                self._display_tool_result(tc.name, result)
                self._emit("tool_result", {"name": tc.name, "result": result})

                if tc.name == "execute_sql":
                    try:
                        data = json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        data = {}
                    if data.get("error"):
                        self._emit("sql_retry", {
                            "attempt": data.get("attempt", 0),
                            "max": self.runtime.max_sql_retries,
                            "error_type": data.get("error_type", ""),
                            "retry_hint": data.get("retry_hint", ""),
                        })

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

        msg = "Text2SQL agent reached maximum iterations without completing."
        self._emit("final_answer", {"text": msg})
        return msg

    # ------------------------------------------------------------------
    # Display (Rich)
    # ------------------------------------------------------------------

    _TOOL_STYLE: dict[str, str] = {
        "match_tables": "blue",
        "get_table_schema": "blue",
        "get_max_partition": "cyan",
        "execute_sql": "green",
        "export_csv": "yellow",
    }

    def _display_tool_call(self, name: str, inputs: dict[str, Any]) -> None:
        color = self._TOOL_STYLE.get(name, "white")
        args_str = ", ".join(f"{k}={repr(v)[:120]}" for k, v in inputs.items())
        self.console.print(
            Panel(args_str or "(no arguments)", title=f"Calling: {name}", border_style=color)
        )

    def _display_tool_result(self, name: str, result: str) -> None:
        try:
            data = json.loads(result)
            if data.get("error"):
                self.console.print(f"  [red]Error:[/red] {str(data['error'])[:200]}")
            elif data.get("success") is True:
                extra = ""
                if "row_count" in data:
                    extra = f" — {data['row_count']} rows, {data.get('elapsed_ms', '?')}ms"
                elif "csv_path" in data:
                    extra = f" — {data['csv_path']}"
                self.console.print(f"  [green]Success[/green]{extra}")
            else:
                self.console.print(f"  [dim]Result received ({len(result)} chars)[/dim]")
        except (json.JSONDecodeError, AttributeError):
            self.console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
