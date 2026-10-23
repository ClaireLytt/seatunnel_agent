"""Text2SQL (Chat BI) agent: natural language -> SQL -> results/CSV.

Supports multiple datasources (Hive, MySQL, SQL Server, Spark SQL, Flink SQL,
ClickHouse, Doris, PostgreSQL).
Mirrors SeaTunnelAgent's ReAct loop and event protocol so the existing UI
streaming machinery (EventCollector) works unchanged.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.panel import Panel

_utf8_stdout: Any = None


def _get_utf8_stdout() -> Any:
    global _utf8_stdout
    if _utf8_stdout is None:
        if hasattr(sys.stdout, "buffer"):
            _utf8_stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace",
                line_buffering=True,
            )
        else:
            _utf8_stdout = sys.stdout
    return _utf8_stdout

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.agent_core.display import display_tool_call, display_tool_result
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.context import truncate_messages
from seatunnel_agent.common.llm import LLMClient
from seatunnel_agent.common.utils import truncate

from .executor import DatabaseConfig
from .prompts import build_text2sql_prompt
from .schema import SchemaStore
from .tools import TOOL_DEFINITIONS, Text2SQLRuntime, execute_text2sql_tool

TOOL_NAMES = [d["name"] for d in TOOL_DEFINITIONS]

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
        metric_store: Any = None,
        example_store: Any = None,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS, agent="text2sql")
        self.runtime = Text2SQLRuntime(
            store=store, metrics=metric_store, ds_type=ds_type, db_config=db_config,
        )
        if example_store is None:
            # Default store is opt-in by content: an absent/empty JSON file
            # keeps behavior identical to before.
            try:
                from .examples import ExampleStore
                example_store = ExampleStore()
            except Exception:
                example_store = None
        self.example_store = example_store
        self.messages: list[dict[str, Any]] = []
        self.last_user_question: str = ""
        self.console = Console(file=_get_utf8_stdout())
        self._on_event = on_event
        self._system_prompt = build_text2sql_prompt(
            store, dialect=ds_type, metric_store=metric_store,
        )

    def set_event_hook(self, on_event: EventCallback | None) -> None:
        """Public seam for attaching/detaching a per-turn event listener
        (used by the streaming REST layer)."""
        self._on_event = on_event

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(event_type, data)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def chat(self, message: str) -> str:
        """Continue a multi-turn conversation, preserving history."""
        self.last_user_question = message
        self.messages.append({"role": "user", "content": self._augment(message)})
        self.console.print(Panel(message, title="Text2SQL", border_style="cyan"))
        return self._agent_loop()

    def run(self, question: str) -> str:
        """Answer a single question with fresh history."""
        self.last_user_question = question
        self.messages = [{"role": "user", "content": self._augment(question)}]
        self.console.print(Panel(question, title="Text2SQL", border_style="cyan"))
        return self._agent_loop()

    def _augment(self, question: str) -> str:
        """Attach verified few-shot examples (BM25 top-K) to the question."""
        from .examples import augment_question

        return augment_question(question, self.example_store)

    def reset(self) -> None:
        self.messages = []
        self.runtime.last_result = None
        self.runtime.last_sql = ""
        self.runtime.sql_retries = 0
        self.runtime.cache.invalidate()

    # ------------------------------------------------------------------
    # Core ReAct loop
    # ------------------------------------------------------------------

    def _agent_loop(self) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        Agent specifics ride the loop's seams: the adapter keeps the legacy
        event protocol (thinking / text / tool_call / tool_result /
        sql_retry / cache_hit / final_answer) and the Rich CLI display;
        ``on_limit`` keeps the legacy step-limit message. The legacy
        per-iteration "step" (iteration/phase) events are not re-emitted -
        no consumer existed.
        """
        def adapter(event_type: str, data: dict[str, Any]) -> None:
            if event_type == "turn":
                if data["thinking"]:
                    self._emit("thinking", {"text": data["thinking"]})
                    self.console.print(
                        Panel(truncate(data["thinking"], 500),
                              title="Thinking", border_style="dim",
                              style="italic dim"))
                if data["text"]:
                    self._emit("text", {"text": data["text"]})
                    self.console.print("\n" + data["text"])
            elif event_type == "tool_call":
                self._display_tool_call(data["name"], data["input"])
                self._emit("tool_call", data)
            elif event_type == "step":
                name, result = data["tool"], data["output"]
                self._display_tool_result(name, result)
                self._emit("tool_result", {"name": name, "result": result})
                if name == "execute_sql":
                    try:
                        parsed = json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        parsed = {}
                    if parsed.get("error"):
                        self._emit("sql_retry", {
                            "attempt": parsed.get("attempt", 0),
                            "max": self.runtime.max_sql_retries,
                            "error_type": parsed.get("error_type", ""),
                            "retry_hint": parsed.get("retry_hint", ""),
                            "failed_sql": parsed.get(
                                "sql", data["input"].get("sql", "")),
                        })
                    elif parsed.get("cached"):
                        self._emit("cache_hit", {
                            "sql": parsed.get("sql", ""),
                            "row_count": parsed.get("row_count", 0),
                        })
            elif event_type in ("text_delta", "usage"):
                self._emit(event_type, data)

        tools = [
            ToolSpec(name=name, description="", input_schema={},
                     run=(lambda _n=name, **kw:
                          execute_text2sql_tool(_n, kw, self.runtime)))
            for name in TOOL_NAMES
        ]
        request = self.messages[-1]["content"]
        loop = ToolLoopAgent(
            self.settings, tools, self._system_prompt, "text2sql",
            max_steps=MAX_LOOP_ITERATIONS, client=self.llm,
            on_event=adapter,  # always: it also drives the Rich CLI display
            truncate=truncate_messages,
            on_limit=lambda: ("Text2SQL agent reached maximum iterations "
                              "without completing."))
        loop.messages = self.messages[:-1]
        result = loop.run(request)
        self.messages = loop.messages
        self._emit("final_answer", {"text": result.reply})
        return result.reply

    # ------------------------------------------------------------------
    # Display (Rich)
    # ------------------------------------------------------------------

    _TOOL_STYLE: dict[str, str] = {
        "match_tables": "blue",
        "get_table_schema": "blue",
        "get_max_partition": "cyan",
        "explain_sql": "magenta",
        "execute_sql": "green",
        "export_csv": "yellow",
        "export_excel": "yellow",
        "export_pdf": "yellow",
    }

    def _display_tool_call(self, name: str, inputs: dict[str, Any]) -> None:
        display_tool_call(self.console, name, inputs, self._TOOL_STYLE)

    @staticmethod
    def _success_extra(data: dict[str, Any]) -> str:
        if "row_count" in data:
            cached = " (cached)" if data.get("cached") else ""
            return f" — {data['row_count']} rows, {data.get('elapsed_ms', '?')}ms{cached}"
        if "csv_path" in data:
            return f" — {data['csv_path']}"
        return ""

    def _display_tool_result(self, name: str, result: str) -> None:
        display_tool_result(self.console, result, self._success_extra)
