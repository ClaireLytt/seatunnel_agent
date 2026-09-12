"""Tests for prompt builder."""

from __future__ import annotations

from seatunnel_agent.prompts import build_system_prompt, SYSTEM_PROMPT, _TASK_HINTS


class TestBuildSystemPrompt:
    def test_default_retries(self):
        prompt = build_system_prompt("run")
        assert "{max_retries}" not in prompt
        assert "3" in prompt

    def test_custom_retries(self):
        prompt = build_system_prompt("run", max_retries=5)
        assert "5" in prompt

    def test_run_hint_included(self):
        prompt = build_system_prompt("run")
        assert "Current Task" in prompt
        assert _TASK_HINTS["run"] in prompt

    def test_validate_hint_included(self):
        prompt = build_system_prompt("validate")
        assert "Do NOT run the job" in prompt

    def test_diagnose_hint_included(self):
        prompt = build_system_prompt("diagnose")
        assert "diagnose" in prompt.lower()

    def test_unknown_task_no_hint(self):
        prompt = build_system_prompt("unknown_task_type")
        assert "Current Task" not in prompt

    def test_system_prompt_has_tools(self):
        assert "run_seatunnel_job" in SYSTEM_PROMPT
        assert "read_log" in SYSTEM_PROMPT
        assert "write_config" in SYSTEM_PROMPT
        assert "validate_config" in SYSTEM_PROMPT

    def test_system_prompt_has_react_pattern(self):
        assert "THINK" in SYSTEM_PROMPT
        assert "ACT" in SYSTEM_PROMPT
        assert "OBSERVE" in SYSTEM_PROMPT

    def test_run_config_hint_included(self):
        prompt = build_system_prompt("run_config")
        assert "Current Task" in prompt
        assert "existing config file" in prompt.lower()

    def test_system_prompt_has_new_tools(self):
        assert "test_connection" in SYSTEM_PROMPT
        assert "list_templates" in SYSTEM_PROMPT
        assert "use_template" in SYSTEM_PROMPT

    def test_system_prompt_has_session_context_awareness(self):
        assert "Session Context" in SYSTEM_PROMPT
        assert "last_config_path" in SYSTEM_PROMPT

    def test_run_hint_mentions_templates(self):
        prompt = build_system_prompt("run")
        assert "template" in prompt.lower() or "list_templates" in prompt

    def test_run_hint_mentions_connection_test(self):
        prompt = build_system_prompt("run")
        assert "test_connection" in prompt
