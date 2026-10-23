"""Ticket loop-06: replace seatunnel's hand-rolled loop with the shared
ToolLoopAgent (stop/delta/truncation/context-hint ride the shared seams)."""
from pathlib import Path

p = Path('src/seatunnel_agent/agents/data/seatunnel/agent.py')
t = p.read_text(encoding='utf-8')

start = t.index("    def _agent_loop(self, system_prompt: str) -> str:")
end = t.index("    def _finish_stopped(self) -> str:")

new = '''    def _agent_loop(self, system_prompt: str) -> str:
        """Run the shared bounded tool-use loop (agent_core.ToolLoopAgent).

        Agent specifics ride the loop's seams: stop_event, text deltas and
        usage via on_event, the session context hint via system_hint, and
        truncate_messages via the truncation policy. Tool wrappers keep
        context tracking and job-retry accounting; when the retry limit is
        hit the wrapper raises the stop signal and the summary turn runs
        here (legacy semantics). The legacy per-iteration "step"
        (iteration/phase) events are not re-emitted - no consumer existed.
        """
        from types import SimpleNamespace

        def adapter(event_type: str, data: dict[str, Any]) -> None:
            if event_type == "turn":
                shim = SimpleNamespace(thinking_text=data["thinking"],
                                       reply_text=data["text"])
                self._emit_parsed_events(shim)
                self._display_parsed(shim)
            elif event_type == "tool_call":
                self._display_tool_call(data["name"], data["input"])
                self._emit("tool_call", data)
            elif event_type == "step":
                self._display_tool_result(data["tool"], data["output"])
                self._emit("tool_result", {"name": data["tool"],
                                           "result": data["output"]})
            elif event_type in ("text_delta", "usage"):
                self._emit(event_type, data)

        self._retry_exhausted = False

        def make_run(name: str):
            def run(**kw: Any) -> str:
                result = execute_tool(name, kw, self.settings)
                self._update_context(name, kw, result)
                if name == "run_seatunnel_job":
                    self._track_retry(result)
                    if self.retry_count >= self.settings.max_retries:
                        self._retry_exhausted = True
                        self.stop_event.set()
                return result
            return run

        tools = [ToolSpec(name=d["name"], description="", input_schema={},
                          run=make_run(d["name"]))
                 for d in TOOL_DEFINITIONS]

        self.stop_event.clear()
        loop = ToolLoopAgent(
            self.settings, tools, system_prompt, "seatunnel",
            max_steps=MAX_LOOP_ITERATIONS, client=self.llm,
            on_event=adapter,  # always: it also drives the Rich CLI display
            stop_event=self.stop_event,
            system_hint=self._build_context_hint,
            truncate=truncate_messages,
            on_limit=lambda: ("Agent loop reached maximum iterations "
                              "without completing."))
        request = self.messages[-1]["content"]
        loop.messages = self.messages[:-1]
        result = loop.run(request)
        self.messages = loop.messages

        if result.stopped and self._retry_exhausted:
            # legacy retry-limit semantics: one forced summary turn
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
        if result.stopped:
            return self._finish_stopped()
        self._emit("final_answer", {"text": result.reply})
        return result.reply

'''
t = t[:start] + new + t[end:]
t = t.replace(
    "from seatunnel_agent.agents.data.seatunnel.tools import TOOL_DEFINITIONS, execute_tool",
    "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec\n"
    "from seatunnel_agent.agents.data.seatunnel.tools import TOOL_DEFINITIONS, execute_tool")
p.write_text(t, encoding='utf-8')
print('loop replaced')
