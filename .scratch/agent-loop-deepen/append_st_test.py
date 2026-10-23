"""Append the loop-06 offline shared-loop test to test_agent.py."""
from pathlib import Path

TEST = '''

class TestSharedLoopMigration:
    def test_agent_runs_on_shared_loop_tool_flow(self):
        """Ticket loop-06: tool flow + event protocol via the shared loop."""
        import unittest.mock as mock

        from tests.conftest import llm_text, llm_tool

        responses = [llm_tool("validate_config",
                              {"config_path": "a.conf"}, cid="c1"),
                     llm_text("all good")]

        events = []
        agent = SeaTunnelAgent(
            SETTINGS, on_event=lambda t, d: events.append(t))
        with mock.patch.object(
                agent.llm, "chat",
                side_effect=lambda *a, **kw: responses.pop(0)), \\
             mock.patch.object(
                agent.llm, "append_assistant",
                side_effect=lambda raw: {"role": "assistant",
                                         "content": [raw]}), \\
             mock.patch.object(
                agent.llm, "build_tool_result_message",
                side_effect=lambda r: {"role": "user", "content": r}), \\
             mock.patch(
                "seatunnel_agent.agents.data.seatunnel.agent.execute_tool",
                return_value='{"success": true}'):
            out = agent.run("validate a.conf")
        assert out == "all good"
        assert "tool_call" in events and "tool_result" in events
        assert events.index("tool_call") < events.index("tool_result")
        assert "final_answer" in events
        # context tracking survived the migration
        assert "a.conf" in agent.context["validated_configs"]
'''

p = Path('tests/test_agent.py')
with p.open('a', encoding='utf-8') as f:
    f.write(TEST)
print('appended')
