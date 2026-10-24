"""Data lineage agent: full-chain table/column lineage analysis.

Two entry points:

- ``static_lineage`` — deterministic, no LLM: query the graph and render the
  Chinese report directly (CLI/API default path).
- ``LineageAgent`` — ReAct loop over the lineage tools for natural-language
  questions like "改这个字段影响哪些下游表". Mirrors SQLReviewAgent's loop
  and event protocol so the existing UI streaming machinery works unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.panel import Panel

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.agent_core.display import display_tool_call, display_tool_result
from seatunnel_agent.agent_core.events import (
    display_turn_panels,
    legacy_event_adapter,
)
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.context import truncate_messages
from seatunnel_agent.common.llm import LLMClient
from seatunnel_agent.common.utils import truncate

from .config import COLUMN_IMPACT_DEPTH, LineageConfig
from .graph import LineageGraph
from .prompts import build_lineage_prompt
from .render import select_mermaid
from .report import LineageReport
from .tools import TOOL_DEFINITIONS, LineageRuntime, execute_lineage_tool

TOOL_NAMES = [d["name"] for d in TOOL_DEFINITIONS]

MAX_LOOP_ITERATIONS = 10

EventCallback = Callable[[str, dict[str, Any]], None]


def static_lineage(
    graph: LineageGraph,
    table: str,
    direction: str = "both",
    depth: int = 3,
    column: str | None = None,
    config: LineageConfig | None = None,
    lang: str = "zh",
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

    mermaid = select_mermaid(chain, impact, config.max_mermaid_nodes,
                             lang=lang)

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
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS, agent="lineage")
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

    # ------------------------------------------------------------------
    # Core ReAct loop
    # ------------------------------------------------------------------

    def _agent_loop(self) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        Agent specifics ride the loop's seams: the adapter keeps the legacy
        event protocol (thinking / text / tool_call / tool_result /
        final_answer) and the Rich CLI display; ``on_limit`` keeps the
        fall-back-to-last-report behavior. The legacy per-iteration "step"
        (iteration/phase) events are not re-emitted - no consumer existed.
        """
        adapter = legacy_event_adapter(
            self._emit,
            display_turn=lambda th, tx: display_turn_panels(
                self.console, th, tx),
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result)

        def on_limit() -> str:
            if self.runtime.last_report:
                return self.runtime.last_report
            return ("Lineage agent reached maximum iterations "
                    "without completing.")

        tools = [
            ToolSpec(name=name, description="", input_schema={},
                     run=(lambda _n=name, **kw:
                          execute_lineage_tool(_n, kw, self.runtime)))
            for name in TOOL_NAMES
        ]
        request = self.messages[-1]["content"]
        loop = ToolLoopAgent(
            self.settings, tools, self._system_prompt, "data_lineage",
            max_steps=MAX_LOOP_ITERATIONS, client=self.llm,
            on_event=adapter,  # always: it also drives the Rich CLI display
            truncate=truncate_messages, on_limit=on_limit)
        loop.messages = self.messages[:-1]
        result = loop.run(request)
        self.messages = loop.messages
        self._emit("final_answer", {"text": result.reply})
        return result.reply

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
        display_tool_call(self.console, name, inputs, self._TOOL_STYLE)

    @staticmethod
    def _success_extra(data: dict[str, Any]) -> str:
        return f" — graph: {data['graph']}" if "graph" in data else ""

    def _display_tool_result(self, name: str, result: str) -> None:
        display_tool_result(self.console, result, self._success_extra)
