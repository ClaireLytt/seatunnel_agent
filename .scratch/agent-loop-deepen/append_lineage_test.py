"""Append the loop-04 offline shared-loop test to test_data_lineage.py."""
from pathlib import Path

TEST = '''

def test_agent_runs_on_shared_loop_with_event_protocol(fixture_graph):
    """Ticket loop-04: tool flow + legacy event names via the shared loop."""
    import unittest.mock as mock

    from seatunnel_agent.agents.data.data_lineage import agent as agent_mod
    from tests.conftest import llm_text, llm_tool

    class ToolFake:
        def __init__(self):
            self.responses = [
                llm_tool("search_tables", {"keyword": "orders"}, cid="c1"),
                llm_text("answer"),
            ]

        def chat(self, system, messages, on_text_delta=None):
            return self.responses.pop(0)

        def append_assistant(self, raw):
            return {"role": "assistant", "content": [raw]}

        def build_tool_result_message(self, results):
            return {"role": "user", "content": results}

    events = []
    with mock.patch.object(agent_mod, "LLMClient",
                           lambda s, tools=None, **kw: ToolFake()):
        ag = agent_mod.LineageAgent(None, graph=fixture_graph,
                                    on_event=lambda t, d: events.append(t))
        out = ag.analyze("where does dwd_orders come from?")
    assert out  # answered through the shared loop
    assert "tool_call" in events and "tool_result" in events
    assert events.index("tool_call") < events.index("tool_result")
    assert "final_answer" in events
'''

p = Path('tests/test_data_lineage.py')
with p.open('a', encoding='utf-8') as f:
    f.write(TEST)
print('appended')
