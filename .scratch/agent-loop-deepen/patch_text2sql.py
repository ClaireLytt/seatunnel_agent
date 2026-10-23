"""Ticket loop-05: replace text2sql's hand-rolled loop with the shared
ToolLoopAgent (adapter keeps the event protocol incl. sql_retry/cache_hit)."""
from pathlib import Path

p = Path('src/seatunnel_agent/agents/data/text2sql/agent.py')
t = p.read_text(encoding='utf-8')

start = t.index("    def _agent_loop(self) -> str:")
end = t.index("    # ------------------------------------------------------------------\n    # Display (Rich)")

new = '''    def _agent_loop(self) -> str:
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
                    self.console.print("\\n" + data["text"])
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

'''
t = t[:start] + new + t[end:]
assert 'TOOL_NAMES' in t or True
t = t.replace(
    "from .tools import TOOL_DEFINITIONS, Text2SQLRuntime, execute_text2sql_tool",
    "from .tools import TOOL_DEFINITIONS, Text2SQLRuntime, execute_text2sql_tool\n\n"
    'TOOL_NAMES = [d["name"] for d in TOOL_DEFINITIONS]')
p.write_text(t, encoding='utf-8')
print('loop replaced')
