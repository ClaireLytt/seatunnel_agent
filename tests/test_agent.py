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

    def test_context_updated_after_write_config(self):
        agent = SeaTunnelAgent(SETTINGS)

        tc = ToolCall(id="t1", name="write_config", input={"config_path": "/tmp/test.conf", "content": "x"})
        resp1 = _tool_response("Writing config", [tc])
        resp2 = _end_response("Done")

        with patch.object(agent.llm, "chat", side_effect=[resp1, resp2]), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}), \
             patch.object(agent.llm, "build_tool_result_message", return_value={"role": "user", "content": []}), \
             patch(
                 "seatunnel_agent.agent.execute_tool",
                 return_value=json.dumps({"success": True, "config_path": "/tmp/test.conf"}),
             ):
            agent.run("write a config")

        assert agent.context["last_config_path"] == "/tmp/test.conf"
        assert "/tmp/test.conf" in agent.context["created_configs"]

    def test_context_updated_after_run_job(self):
        agent = SeaTunnelAgent(SETTINGS)

        tc = ToolCall(id="t1", name="run_seatunnel_job", input={"config_path": "/tmp/j.conf"})
        resp1 = _tool_response("Running", [tc])
        resp2 = _end_response("Failed")

        with patch.object(agent.llm, "chat", side_effect=[resp1, resp2]), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}), \
             patch.object(agent.llm, "build_tool_result_message", return_value={"role": "user", "content": []}), \
             patch(
                 "seatunnel_agent.agent.execute_tool",
                 return_value=json.dumps({"success": False, "exit_code": 1, "stderr": "conn refused"}),
             ):
            agent.run("run job")

        assert agent.context["last_job_success"] is False
        assert agent.context["last_job_error"]

    def test_step_events_emitted(self):
        events = []
        agent = SeaTunnelAgent(SETTINGS, on_event=lambda t, d: events.append({"type": t, **d}))
        resp = _end_response("Done")

        with patch.object(agent.llm, "chat", return_value=resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            agent.run("test")

        step_events = [e for e in events if e["type"] == "step"]
        assert len(step_events) >= 1
        assert step_events[0]["iteration"] == 1
        assert step_events[0]["phase"] == "thinking"

    def test_context_hint_in_prompt(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.context["last_config_path"] = "/tmp/my.conf"

        captured_prompts = []
        original_chat = agent.llm.chat

        def capturing_chat(prompt, *args, **kwargs):
            captured_prompts.append(prompt)
            return _end_response("ok")

        with patch.object(agent.llm, "chat", side_effect=capturing_chat), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            agent.run("test")

        assert any("Session Context" in p for p in captured_prompts)
        assert any("/tmp/my.conf" in p for p in captured_prompts)


class TestUpdateContext:
    def _run_tool(self, agent, tool_name, tool_input, result_data):
        agent._update_context(tool_name, tool_input, json.dumps(result_data))

    def test_validate_config_tracks_path(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(agent, "validate_config", {"config_path": "/tmp/v.conf"}, {"valid": True})
        assert "/tmp/v.conf" in agent.context["validated_configs"]

    def test_validate_config_no_duplicate(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(agent, "validate_config", {"config_path": "/tmp/v.conf"}, {"valid": True})
        self._run_tool(agent, "validate_config", {"config_path": "/tmp/v.conf"}, {"valid": True})
        assert agent.context["validated_configs"].count("/tmp/v.conf") == 1

    def test_read_config_sets_last_path(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(agent, "read_config", {"config_path": "/tmp/r.conf"}, {"content": "x"})
        assert agent.context["last_config_path"] == "/tmp/r.conf"

    def test_list_templates_sets_flag(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(agent, "list_templates", {}, {"templates": [], "count": 0})
        assert agent.context.get("last_template_lookup") is True

    def test_test_connection_reachable(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(
            agent, "test_connection",
            {"host": "db.local", "port": 3306},
            {"reachable": True},
        )
        assert "db.local:3306" in agent.context["last_connection_test"]
        assert "reachable" in agent.context["last_connection_test"]

    def test_test_connection_unreachable(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(
            agent, "test_connection",
            {"host": "db.local", "port": 3306},
            {"reachable": False},
        )
        assert "unreachable" in agent.context["last_connection_test"]

    def test_use_template_tracks_config(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(
            agent, "use_template",
            {"template_name": "fake_to_console", "parameters": {}, "config_path": "/tmp/tpl.conf"},
            {"success": True, "config_path": "/tmp/tpl.conf"},
        )
        assert agent.context["last_config_path"] == "/tmp/tpl.conf"
        assert "/tmp/tpl.conf" in agent.context["created_configs"]

    def test_run_job_success_resets_error(self):
        agent = SeaTunnelAgent(SETTINGS)
        self._run_tool(agent, "run_seatunnel_job", {"config_path": "/tmp/j.conf"}, {"success": True})
        assert agent.context["last_job_success"] is True
        assert agent.context["last_job_error"] is None

    def test_invalid_json_ignored(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent._update_context("write_config", {}, "not json")
        assert agent.context["last_config_path"] is None


class TestBuildContextHint:
    def test_empty_context(self):
        agent = SeaTunnelAgent(SETTINGS)
        hint = agent._build_context_hint()
        assert "Session Context" in hint
        assert "No config files" in hint

    def test_with_config_path(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.context["last_config_path"] = "/tmp/my.conf"
        hint = agent._build_context_hint()
        assert "/tmp/my.conf" in hint
        assert "No config files" not in hint

    def test_with_job_result(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.context["last_job_success"] = False
        agent.context["last_job_error"] = "connection refused"
        hint = agent._build_context_hint()
        assert "Failed" in hint
        assert "connection refused" in hint

    def test_with_validated_configs(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.context["validated_configs"] = ["/tmp/a.conf", "/tmp/b.conf"]
        hint = agent._build_context_hint()
        assert "/tmp/a.conf" in hint
        assert "Validated" in hint

    def test_with_connection_test(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.context["last_connection_test"] = "db:3306 → reachable"
        hint = agent._build_context_hint()
        assert "db:3306" in hint

    def test_do_not_guess_instruction(self):
        agent = SeaTunnelAgent(SETTINGS)
        hint = agent._build_context_hint()
        assert "Do NOT guess file paths" in hint


class TestTrackRetry:
    def test_success_resets_count(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent.retry_count = 2
        agent._track_retry(json.dumps({"success": True}))
        assert agent.retry_count == 0

    def test_failure_increments(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent._track_retry(json.dumps({"success": False}))
        assert agent.retry_count == 1

    def test_invalid_json_increments(self):
        agent = SeaTunnelAgent(SETTINGS)
        agent._track_retry("not json")
        assert agent.retry_count == 1


class TestEntryPoints:
    def test_chat_preserves_history(self):
        agent = SeaTunnelAgent(SETTINGS)
        resp = _end_response("reply1")
        with patch.object(agent.llm, "chat", return_value=resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            agent.chat("first")
        assert len(agent.messages) >= 2
        resp2 = _end_response("reply2")
        with patch.object(agent.llm, "chat", return_value=resp2), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            agent.chat("second")
        user_msgs = [m for m in agent.messages if m.get("role") == "user"]
        assert len(user_msgs) == 2

    def test_validate_only(self):
        agent = SeaTunnelAgent(SETTINGS)
        resp = _end_response("Valid config")
        with patch.object(agent.llm, "chat", return_value=resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            result = agent.validate_only("/tmp/job.conf")
        assert result == "Valid config"

    def test_diagnose_log(self):
        agent = SeaTunnelAgent(SETTINGS)
        resp = _end_response("Root cause found")
        with patch.object(agent.llm, "chat", return_value=resp), \
             patch.object(agent.llm, "append_assistant", return_value={"role": "assistant", "content": "ok"}):
            result = agent.diagnose_log("/tmp/seatunnel.log")
        assert result == "Root cause found"
