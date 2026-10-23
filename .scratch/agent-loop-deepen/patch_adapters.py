"""遗留修复 2: converge the four per-agent event adapters onto
agent_core.events.legacy_event_adapter."""
from pathlib import Path

COMMON_ADAPTER = '''        def adapter(event_type: str, data: dict[str, Any]) -> None:
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
'''

SHARED_CALL = '''        adapter = legacy_event_adapter(
            self._emit,
            display_turn=lambda th, tx: display_turn_panels(
                self.console, th, tx),
            display_tool_call=self._display_tool_call,
            display_tool_result=self._display_tool_result)
'''

IMPORT_OLD = "from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec"
IMPORT_NEW = ("from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec\n"
              "from seatunnel_agent.agent_core.events import (\n"
              "    display_turn_panels,\n"
              "    legacy_event_adapter,\n"
              ")")

for path in ("src/seatunnel_agent/agents/data/sql_review/agent.py",
             "src/seatunnel_agent/agents/data/data_lineage/agent.py"):
    p = Path(path)
    t = p.read_text(encoding='utf-8')
    assert t.count(COMMON_ADAPTER) == 1, (path, t.count(COMMON_ADAPTER))
    t = t.replace(COMMON_ADAPTER, SHARED_CALL)
    assert t.count(IMPORT_OLD) == 1
    t = t.replace(IMPORT_OLD, IMPORT_NEW)
    p.write_text(t, encoding='utf-8')
    print(path, 'ok')
