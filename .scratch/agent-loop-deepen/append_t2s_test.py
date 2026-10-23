"""Append the loop-05 offline shared-loop test to test_text2sql.py."""
from pathlib import Path

TEST = '''

def test_agent_runs_on_shared_loop_with_event_protocol(store):
    """Ticket loop-05: tool flow + legacy event names via the shared loop."""
    import json as _json
    import unittest.mock as mock

    from seatunnel_agent.agents.data.text2sql import agent as agent_mod
    from tests.conftest import llm_text, llm_tool

    class ToolFake:
        def __init__(self):
            self.responses = [
                llm_tool("execute_sql", {"sql": "select 1"}, cid="c1"),
                llm_text("done"),
            ]

        def chat(self, system, messages, on_text_delta=None):
            return self.responses.pop(0)

        def append_assistant(self, raw):
            return {"role": "assistant", "content": [raw]}

        def build_tool_result_message(self, results):
            return {"role": "user", "content": results}

    events = []
    with mock.patch.object(agent_mod, "LLMClient",
                           lambda s, tools=None, **kw: ToolFake()), \\
         mock.patch.object(agent_mod, "execute_text2sql_tool",
                           lambda n, i, rt: _json.dumps({"rows": []})):
        ag = agent_mod.Text2SQLAgent(
            None, store, on_event=lambda t, d: events.append(t))
        out = ag.run("how many orders today?")
    assert out == "done"
    assert "tool_call" in events and "tool_result" in events
    assert events.index("tool_call") < events.index("tool_result")
    assert "final_answer" in events
'''

p = Path('tests/test_text2sql.py')
with p.open('a', encoding='utf-8') as f:
    f.write(TEST)
print('appended')
