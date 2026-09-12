from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from seatunnel_agent.agent import SeaTunnelAgent
from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMResponse, ToolCall

SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home="/tmp/seatunnel",
    seatunnel_bin="/tmp/seatunnel/bin/seatunnel.sh",
    max_retries=2,
)


def _end_response(text: str) -> LLMResponse:
    return LLMResponse(
        wants_tool_use=False,
        tool_calls=[],
        thinking_text="",
        reply_text=text,
        raw_content=text,
    )


def _tool_response(text: str, tool_calls: list[ToolCall]) -> LLMResponse:
    return LLMResponse(
        wants_tool_use=True,
        tool_calls=tool_calls,
        thinking_text="",
        reply_text=text,
        raw_content=text,
    )


class TestAgentLoop:
    def test_simple_end_turn(self):
        agent = SeaTunnelAgent(SETTINGS)
        mock_resp = _end_response("All done!")

        with patch.object(agent.llm, "chat", return_value=mock_resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "All done!"}):
            result = agent.run("test task")

        assert result == "All done!"

    def test_tool_call_then_end(self):
        agent = SeaTunnelAgent(SETTINGS)

        resp1 = _tool_response(
            "Let me validate the config.",
            [ToolCall(id="tool_001", name="validate_config", input={"config_path": "/tmp/job.conf"})],
        )
        resp2 = _end_response("Config is valid.")

        with patch.object(agent.llm, "chat", side_effect=[resp1, resp2]), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}), \
             patch.object(agent.llm, "build_tool_result_message", return_value={"role": "user", "content": []}), \
             patch(
                 "seatunnel_agent.agent.execute_tool",
                 return_value=json.dumps({"valid": True, "errors": [], "warnings": [], "sections_found": ["source", "sink"]}),
             ):
            result = agent.run("validate my config")

        assert "valid" in result.lower() or "Config" in result

    def test_retry_limit_reached(self):
        agent = SeaTunnelAgent(SETTINGS)

        fail_result = json.dumps({"success": False, "exit_code": 1, "stderr": "error"})
        tc = ToolCall(id="tool_001", name="run_seatunnel_job", input={"config_path": "/tmp/job.conf"})
        tool_resp = _tool_response("Running...", [tc])
        final_resp = _end_response("Giving up after retries.")

        responses = [tool_resp, tool_resp, tool_resp, final_resp]

        with patch.object(agent.llm, "chat", side_effect=responses), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}), \
             patch.object(agent.llm, "build_tool_result_message", return_value={"role": "user", "content": []}), \
             patch("seatunnel_agent.agent.execute_tool", return_value=fail_result):
            result = agent.run_with_config("/tmp/job.conf")

        assert agent.retry_count >= SETTINGS.max_retries

    def test_max_iterations_safety(self):
        agent = SeaTunnelAgent(SETTINGS)

        tc = ToolCall(id="tool_001", name="read_config", input={"config_path": "/tmp/job.conf"})
        loop_resp = _tool_response("", [tc])

        with patch.object(agent.llm, "chat", return_value=loop_resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}), \
             patch.object(agent.llm, "build_tool_result_message", return_value={"role": "user", "content": []}), \
             patch(
                 "seatunnel_agent.agent.execute_tool",
                 return_value=json.dumps({"content": "fake config"}),
             ):
            result = agent.run("infinite loop test")

        assert "maximum iterations" in result.lower()
