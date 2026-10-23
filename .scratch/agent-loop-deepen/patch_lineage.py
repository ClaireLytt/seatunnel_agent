"""Ticket loop-04: replace data_lineage's hand-rolled loop with the shared
ToolLoopAgent (same adapter pattern as sql_review, loop-03)."""
from pathlib import Path

p = Path('src/seatunnel_agent/agents/data/data_lineage/agent.py')
t = p.read_text(encoding='utf-8')

start = t.index("    def _agent_loop(self) -> str:")
end = t.index("    # ------------------------------------------------------------------\n    # Display (Rich)")

new = '''    def _agent_loop(self) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        Agent specifics ride the loop's seams: the adapter keeps the legacy
        event protocol (thinking / text / tool_call / tool_result /
        final_answer) and the Rich CLI display; ``on_limit`` keeps the
        fall-back-to-last-report behavior. The legacy per-iteration "step"
        (iteration/phase) events are not re-emitted - no consumer existed.
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
                self._display_tool_result(data["tool"], data["output"])
                self._emit("tool_result", {"name": data["tool"],
                                           "result": data["output"]})
            elif event_type in ("text_delta", "usage"):
                self._emit(event_type, data)

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

'''
t = t[:start] + new + t[end:]
p.write_text(t, encoding='utf-8')
print('loop replaced')
