"""SQL Code Review agent: static lint + LLM semantic review -> CR report.

Supports Hive SQL, Spark SQL, Flink SQL and MaxCompute SQL. Pure static
analysis — the SQL is never executed. Mirrors Text2SQLAgent's ReAct loop
and event protocol so the existing UI streaming machinery works unchanged.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel

from ..config import Settings
from ..context import truncate_messages
from ..llm import LLMClient
from ..text2sql.schema import SchemaStore
from ..utils import truncate
from .config import ReviewConfig
from .i18n import normalize_lang, sr
from .lineage import extract_table_lineage
from .linter import lint_sql, normalize_dialect
from .prompts import build_review_prompt
from .report import ReviewReport, render_report
from .tools import TOOL_DEFINITIONS, SQLReviewRuntime, execute_review_tool

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
    ) -> None:
        self.settings = settings
        self.llm = LLMClient(settings, tools=TOOL_DEFINITIONS)
        self.dialect = normalize_dialect(dialect)
        self.store = store
        self.config = config
        self.lang = normalize_lang(lang)
        self.runtime: SQLReviewRuntime | None = None
        self.messages: list[dict[str, Any]] = []
        self.console = Console()
        self._on_event = on_event
        self._system_prompt = build_review_prompt(self.dialect, store, lang=self.lang)

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

        answer = self._agent_loop()
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

                result = execute_review_tool(tc.name, tc.input, self.runtime)

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

        # Fell out of the loop — fall back to whatever review exists.
        if self.runtime and self.runtime.last_report:
            self._emit("final_answer", {"text": self.runtime.last_report})
            return self.runtime.last_report
        msg = "SQL Review agent reached maximum iterations without completing."
        self._emit("final_answer", {"text": msg})
        return msg

    # ------------------------------------------------------------------
    # Display (Rich)
    # ------------------------------------------------------------------

    _TOOL_STYLE: dict[str, str] = {
        "lint_sql": "blue",
        "get_table_schema": "cyan",
        "submit_review": "green",
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
                if "finding_count" in data:
                    extra = f" — {data['finding_count']} finding(s)"
                self.console.print(f"  [green]Success[/green]{extra}")
            else:
                self.console.print(f"  [dim]Result received ({len(result)} chars)[/dim]")
        except (json.JSONDecodeError, AttributeError):
            self.console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
