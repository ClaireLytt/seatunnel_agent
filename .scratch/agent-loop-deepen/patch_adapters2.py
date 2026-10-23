"""遗留修复 2 (part 2): text2sql + seatunnel onto the shared adapter."""
from pathlib import Path

# ── text2sql ──
p = Path('src/seatunnel_agent/agents/data/text2sql/agent.py')
t = p.read_text(encoding='utf-8')
start = t.index('        def adapter(event_type: str, data: dict[str, Any]) -> None:')
end = t.index('        tools = [')
new = '''        def step_extra(data: dict[str, Any]) -> None:
            if data["tool"] != "execute_sql":
                return
            try:
                parsed = json.loads(data["output"])
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

        adapter = legacy_event_adapter(
            self._emit,
            display_turn=lambda th, tx: display_turn_panels(
                self.console, th, tx),
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result,
            step_extra=step_extra)

'''
t = t[:start] + new + t[end:]
t = t.replace(
    "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec",
    "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec\n"
    "from seatunnel_agent.agent_core.events import (\n"
    "    display_turn_panels,\n"
    "    legacy_event_adapter,\n"
    ")")
p.write_text(t, encoding='utf-8')
print('text2sql ok')

# ── seatunnel ──
p = Path('src/seatunnel_agent/agents/data/seatunnel/agent.py')
t = p.read_text(encoding='utf-8')
old = '''        from types import SimpleNamespace

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
'''
new = '''        from types import SimpleNamespace

        def display_turn(thinking: str, text: str) -> None:
            self._display_parsed(SimpleNamespace(thinking_text=thinking,
                                                 reply_text=text))

        adapter = legacy_event_adapter(
            self._emit,
            display_turn=display_turn,
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result)
'''
assert t.count(old) == 1
t = t.replace(old, new)
t = t.replace(
    "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec",
    "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec\n"
    "from seatunnel_agent.agent_core.events import legacy_event_adapter")
p.write_text(t, encoding='utf-8')
print('seatunnel ok')
