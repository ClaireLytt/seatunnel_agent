"""SQL Code Review agent: static lint + LLM semantic review -> CR report.

Supports Hive SQL, Spark SQL, Flink SQL and MaxCompute SQL. Pure static
analysis — the SQL is never executed. Mirrors Text2SQLAgent's ReAct loop
and event protocol so the existing UI streaming machinery works unchanged.
"""

from __future__ import annotations

import os
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
from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
from seatunnel_agent.common.config import Settings
from seatunnel_agent.common.context import truncate_messages
from seatunnel_agent.common.llm import LLMClient
from seatunnel_agent.common.utils import normalize_lang, truncate

from .config import ReviewConfig
from .i18n import sr
from .lineage import extract_table_lineage
from .linter import lint_sql, normalize_dialect
from .prompts import build_review_prompt
from .report import ReviewReport, render_report
from .tools import TOOL_DEFINITIONS, SQLReviewRuntime, execute_review_tool

TOOL_NAMES = [d["name"] for d in TOOL_DEFINITIONS]


def _max_iterations() -> int:
    try:
        return max(1, int(os.getenv("SQLREVIEW_MAX_ITERATIONS", "10")))
    except ValueError:
        return 10


MAX_LOOP_ITERATIONS = _max_iterations()

EventCallback = Callable[[str, dict[str, Any]], None]


def static_review_report(
    sql: str,
    dialect: str = "hive",
    store: SchemaStore | None = None,
    config: ReviewConfig | None = None,
) -> ReviewReport:
    """Linter-only review (no LLM): run deterministic rules, return the report object."""
    dialect = normalize_dialect(dialect)
    findings = lint_sql(sql, dialect, store=store, config=config)
    return ReviewReport(
        findings=findings, dialect=dialect,
        lineage=extract_table_lineage(sql, store=store),
    )


def static_review(
    sql: str,
    dialect: str = "hive",
    store: SchemaStore | None = None,
    config: ReviewConfig | None = None,
) -> str:
    """Linter-only review (no LLM): run deterministic rules, render the report."""
    return render_report(static_review_report(sql, dialect, store=store, config=config))


class SQLReviewAgent:
    def __init__(
        self,
        settings: Settings,
        dialect: str = "hive",
        store: SchemaStore | None = None,
        config: ReviewConfig | None = None,
        on_event: EventCallback | None = None,
        lang: str = "zh",
        use_cache: bool = True,
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS, agent="sql_review")
        self.dialect = normalize_dialect(dialect)
        self.store = store
        self.config = config
        self.lang = normalize_lang(lang)
        self.runtime: SQLReviewRuntime | None = None
        self.messages: list[dict[str, Any]] = []
        self.console = Console()
        self._on_event = on_event
        self._system_prompt = build_review_prompt(self.dialect, store, lang=self.lang)
        from .cache import ReviewCache, cache_enabled
        self._cache = ReviewCache() if (use_cache and cache_enabled()) else None

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(event_type, data)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def review(self, sql: str, instructions: str = "") -> str:
        """Review one SQL statement/script and return the CR report."""
        sql = sql.strip()
        if not sql:
            return sr(self.lang, "sr_no_sql")
        self.runtime = SQLReviewRuntime(
            sql=sql, dialect=self.dialect, store=self.store, config=self.config,
            lang=self.lang,
        )
        if self.lang == "en":
            prompt = (f"Please code-review the following {self.dialect} SQL:"
                      f"\n\n```sql\n{sql}\n```")
            if instructions:
                prompt += f"\n\nAdditional instructions: {instructions}"
        else:
            prompt = f"请对以下 {self.dialect} SQL 做 Code Review：\n\n```sql\n{sql}\n```"
            if instructions:
                prompt += f"\n\n补充说明：{instructions}"
        self.messages = [{"role": "user", "content": prompt}]
        self.console.print(Panel(truncate(sql, 800), title="SQL Review", border_style="cyan"))

        # ── LLM review cache: same SQL + dialect + lang + model + rules +
        # schema → replay the stored conclusion instead of spending tokens ──
        model = getattr(self.settings, "model_name", "") or ""
        if self._cache is not None and not instructions:
            hit = self._cache.get(sql, self.dialect, lang=self.lang,
                                  model=model, config=self.config,
                                  store=self.store)
            if hit is not None:
                report_md, report = hit
                self.runtime.report = report
                self.runtime.last_report = report_md
                self.messages.append({"role": "assistant", "content": report_md})
                self._emit("cache_hit", {"dialect": self.dialect})
                self.console.print(
                    "[dim]" + sr(self.lang, "sr_cache_hit") + "[/dim]"
                )
                return report_md

        answer = self._agent_loop()
        if (self._cache is not None and not instructions
                and self.runtime.report is not None and self.runtime.last_report):
            self._cache.put(sql, self.dialect, self.runtime.report,
                            self.runtime.last_report, lang=self.lang,
                            model=model, config=self.config, store=self.store)
        # The prompt asks the model to echo the rendered report verbatim; if it
        # paraphrased instead, prefer the deterministic render. The markers come
        # from i18n so a wording change there cannot silently break this check.
        markers = {
            sr(lg, "sr_report_title").lstrip("#").strip() for lg in ("zh", "en")
        }
        if self.runtime.last_report and not any(m in answer for m in markers):
            return self.runtime.last_report
        return answer

    def chat(self, message: str) -> str:
        """Follow-up conversation about the last review (e.g. ask for a fix)."""
        if not self.messages:
            return self.review(message)
        self.messages.append({"role": "user", "content": message})
        self.console.print(Panel(message, title="SQL Review", border_style="cyan"))
        return self._agent_loop()

    def reset(self) -> None:
        self.messages = []
        self.runtime = None

    # ------------------------------------------------------------------
    # Core ReAct loop
    # ------------------------------------------------------------------

    def _agent_loop(self) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        The agent-specific pieces ride the loop's seams: the on_event
        adapter below keeps this agent's legacy event protocol (thinking /
        text / tool_call / tool_result / final_answer) and the Rich CLI
        display; ``on_limit`` keeps the fall-back-to-last-report behavior
        (no forced summary turn). The legacy per-iteration "step" events
        (iteration/phase) are not re-emitted — no consumer existed.
        """
        adapter = legacy_event_adapter(
            self._emit,
            display_turn=lambda th, tx: display_turn_panels(
                self.console, th, tx),
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result)

        def on_limit() -> str:
            if self.runtime and self.runtime.last_report:
                return self.runtime.last_report
            return ("SQL Review agent reached maximum iterations "
                    "without completing.")

        tools = [
            ToolSpec(name=name, description="", input_schema={},
                     run=(lambda _n=name, **kw:
                          execute_review_tool(_n, kw, self.runtime)))
            for name in TOOL_NAMES
        ]
        # history handoff: the loop appends the pending user turn itself
        request = self.messages[-1]["content"]
        loop = ToolLoopAgent(
            self.settings, tools, self._system_prompt, "sql_review",
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
        "lint_sql": "blue",
        "get_table_schema": "cyan",
        "submit_review": "green",
    }

    def _display_tool_call(self, name: str, inputs: dict[str, Any]) -> None:
        display_tool_call(self.console, name, inputs, self._TOOL_STYLE)

    @staticmethod
    def _success_extra(data: dict[str, Any]) -> str:
        if "finding_count" in data:
            return f" — {data['finding_count']} finding(s)"
        return ""

    def _display_tool_result(self, name: str, result: str) -> None:
        display_tool_result(self.console, result, self._success_extra)
