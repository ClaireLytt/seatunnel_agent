"""Data lineage agent: full-chain table/column lineage analysis.

Two entry points:

- ``static_lineage`` — deterministic, no LLM: query the graph and render the
  Chinese report directly (CLI/API default path).
- ``LineageAgent`` — ReAct loop over the lineage tools for natural-language
  questions like "改这个字段影响哪些下游表". Mirrors SQLReviewAgent's loop
  and event protocol so the existing UI streaming machinery works unchanged.
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
from .config import COLUMN_IMPACT_DEPTH, LineageConfig
from .graph import LineageGraph
from .prompts import build_lineage_prompt
from .render import select_mermaid
from .report import LineageReport
from .tools import TOOL_DEFINITIONS, LineageRuntime, execute_lineage_tool

MAX_LOOP_ITERATIONS = 10

EventCallback = Callable[[str, dict[str, Any]], None]


def static_lineage(
    graph: LineageGraph,
    table: str,
    direction: str = "both",
    depth: int = 3,
    column: str | None = None,
    config: LineageConfig | None = None,
) -> LineageReport:
    """Deterministic lineage analysis (no LLM): query the graph, build a report."""
    config = config or LineageConfig()
    depth = max(1, min(depth, config.max_depth))

    if direction == "upstream":
        chain = graph.upstream_of(table, depth, config.max_nodes)
    elif direction == "downstream":
        chain = graph.downstream_of(table, depth, config.max_nodes)
    else:
        direction = "both"
        chain = graph.full_chain(table, depth, depth, config.max_nodes)

    impact = None
    if column and not chain.missing_root:
        impact = graph.impact_of_column(
            table, column, depth=COLUMN_IMPACT_DEPTH, max_nodes=config.max_nodes,
        )

    mermaid = select_mermaid(chain, impact, config.max_mermaid_nodes)

    return LineageReport(
        root_table=chain.root,
        direction=direction,
        chain=chain,
        column_impact=impact,
        mermaid=mermaid,
    )


class LineageAgent:
    def __init__(
        self,
        settings: Settings,
        graph: LineageGraph | None = None,
        config: LineageConfig | None = None,
        sql_dir: str | None = None,
        sql_dialect: str = "hive",
        seatunnel_dir: str | None = None,
        hive_available: bool = False,
        meta_table: str | None = None,
        partition: str | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS)
        self.config = config or LineageConfig()
        self.runtime = LineageRuntime(
            graph=graph if graph is not None else LineageGraph(),
            config=self.config,
            sql_dir=sql_dir,
            sql_dialect=sql_dialect,
            seatunnel_dir=seatunnel_dir,
            hive_available=hive_available,
            meta_table=meta_table or self.config.meta_table,
            partition=partition,
        )
        self.messages: list[dict[str, Any]] = []
        self.console = Console()
        self._on_event = on_event
        self._system_prompt = build_lineage_prompt(
            self.runtime.graph, self.config, hive_available, sql_dir,
            seatunnel_dir=seatunnel_dir,
        )

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(event_type, data)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def analyze(self, question: str) -> str:
        """Answer one lineage question and return the rendered Chinese report."""
        question = question.strip()
        if not question:
            return "请提供要分析的血缘问题。"
        self.runtime.reset_question_state()
        self.messages = [{"role": "user", "content": question}]
        self.console.print(Panel(truncate(question, 800), title="Lineage", border_style="cyan"))

        answer = self._agent_loop()
        # The prompt asks the model to echo the rendered report verbatim; if it
        # paraphrased instead, prefer the deterministic render.
        if self.runtime.last_report and "血缘分析报告" not in answer:
            return self.runtime.last_report
        return answer

    def chat(self, message: str) -> str:
        """Follow-up conversation about the loaded lineage graph."""
        if not self.messages:
            return self.analyze(message)
        # 追问是新的问题：清掉上一轮的 per-question 状态，保留图和对话历史。
        self.runtime.reset_question_state()
        self.messages.append({"role": "user", "content": message})
        self.console.print(Panel(message, title="Lineage", border_style="cyan"))
        return self._agent_loop()

    def reset(self) -> None:
        """Clear the conversation; the loaded graph is kept."""
        self.messages = []
        self.runtime.reset_question_state()

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

                result = execute_lineage_tool(tc.name, tc.input, self.runtime)

                self._display_tool_result(tc.name, result)
                self._emit("tool_result", {"name": tc.name, "result": result})

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

        # Fell out of the loop — fall back to whatever report exists.
        if self.runtime.last_report:
            self._emit("final_answer", {"text": self.runtime.last_report})
            return self.runtime.last_report
        msg = "Lineage agent reached maximum iterations without completing."
        self._emit("final_answer", {"text": msg})
        return msg

    # ------------------------------------------------------------------
    # Display (Rich)
    # ------------------------------------------------------------------

    _TOOL_STYLE: dict[str, str] = {
        "load_lineage_from_hive": "magenta",
        "load_lineage_from_sql": "magenta",
        "load_lineage_from_seatunnel": "magenta",
        "get_upstream": "blue",
        "get_downstream": "blue",
        "get_full_chain": "blue",
        "impact_analysis": "yellow",
        "find_path": "blue",
        "sla_impact": "yellow",
        "health_check": "yellow",
        "search_tables": "cyan",
        "get_table_detail": "cyan",
        "submit_lineage_report": "green",
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
                if "graph" in data:
                    extra = f" — graph: {data['graph']}"
                self.console.print(f"  [green]Success[/green]{extra}")
            else:
                self.console.print(f"  [dim]Result received ({len(result)} chars)[/dim]")
        except (json.JSONDecodeError, AttributeError):
            self.console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
