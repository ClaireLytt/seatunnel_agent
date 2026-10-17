"""Tests for the SeaTunnel event->chat rendering helpers (rendering.py)."""

from __future__ import annotations

import json
import threading
import time

from seatunnel_agent.agents.data.seatunnel.rendering import (
    EventCollector,
    _format_events_as_chat,
)


class TestFormatEvents:
    def test_step_event(self):
        events = [{"type": "step", "iteration": 1, "max": 20, "phase": "thinking"}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "Step 1" in msgs[0]["content"]
        assert "/20" not in msgs[0]["content"]
        assert "Thinking" in msgs[0]["content"]

    def test_step_executing_tools(self):
        events = [{"type": "step", "iteration": 2, "max": 20, "phase": "executing_tools"}]
        msgs = _format_events_as_chat(events)
        assert "Step 2" in msgs[0]["content"]
        assert "Executing tools" in msgs[0]["content"]

    def test_text_delta_accumulation(self):
        events = [
            {"type": "text_delta", "text": "Hello "},
            {"type": "text_delta", "text": "world"},
        ]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "Hello world" in msgs[0]["content"]
        assert "▌" in msgs[0]["content"]

    def test_text_delta_replaced_by_text(self):
        events = [
            {"type": "text_delta", "text": "partial"},
            {"type": "text", "text": "Full complete text"},
        ]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "Full complete text"

    def test_reachable_result(self):
        events = [{
            "type": "tool_result",
            "name": "test_connection",
            "result": json.dumps({"reachable": True, "message": "localhost:3306 is reachable (5ms)"}),
        }]
        msgs = _format_events_as_chat(events)
        assert "✅" in msgs[0]["content"]
        assert "reachable" in msgs[0]["content"]

    def test_unreachable_result(self):
        events = [{
            "type": "tool_result",
            "name": "test_connection",
            "result": json.dumps({"reachable": False, "message": "Cannot reach host"}),
        }]
        msgs = _format_events_as_chat(events)
        assert "❌" in msgs[0]["content"]

    def test_diff_in_write_config_result(self):
        events = [{
            "type": "tool_result",
            "name": "write_config",
            "result": json.dumps({
                "success": True,
                "diff": "--- old\n+++ new\n-old line\n+new line\n",
                "had_changes": True,
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "diff" in msgs[0]["content"].lower()
        assert "old line" in msgs[0]["content"]

    def test_templates_result(self):
        events = [{
            "type": "tool_result",
            "name": "list_templates",
            "result": json.dumps({
                "templates": [
                    {"name": "fake_to_console", "description": "Test template"},
                ],
                "count": 1,
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "fake_to_console" in msgs[0]["content"]

    def test_tool_call_new_emojis(self):
        for tool_name in ("test_connection", "list_templates", "use_template"):
            events = [{"type": "tool_call", "name": tool_name, "input": {}}]
            msgs = _format_events_as_chat(events)
            assert len(msgs) == 1
            assert tool_name in msgs[0]["content"]


class TestFormatEventsThinkingAndFinal:
    def test_thinking_event(self):
        events = [{"type": "thinking", "text": "Analyzing the config..."}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "Analyzing" in msgs[0]["content"]

    def test_final_answer_event_not_rendered(self):
        events = [{"type": "final_answer", "text": "The config is valid."}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 0

    def test_tool_call_event(self):
        events = [{"type": "tool_call", "name": "write_config", "input": {"config_path": "/tmp/x.conf"}}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "write_config" in msgs[0]["content"]

    def test_generic_tool_result(self):
        events = [{"type": "tool_result", "name": "read_config", "result": json.dumps({"content": "env{}"})}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1


class TestEventCollector:
    def test_on_event_adds_to_list(self):
        ec = EventCollector()
        ec.on_event("step", {"iteration": 1})
        assert len(ec.snapshot()) == 1
        assert ec.snapshot()[0]["type"] == "step"

    def test_final_answer_sets_done(self):
        ec = EventCollector()
        assert not ec.done
        ec.on_event("final_answer", {"text": "done"})
        assert ec.done

    def test_snapshot_is_copy(self):
        ec = EventCollector()
        ec.on_event("text", {"text": "hi"})
        snap = ec.snapshot()
        ec.on_event("text", {"text": "more"})
        assert len(snap) == 1
        assert len(ec.snapshot()) == 2

    def test_wait_for_event_returns_immediately_on_set(self):
        ec = EventCollector()
        ec.on_event("step", {"iteration": 1})
        start = time.monotonic()
        ec.wait_for_event(timeout=5.0)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0

    def test_wait_for_event_timeout(self):
        ec = EventCollector()
        start = time.monotonic()
        ec.wait_for_event(timeout=0.05)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04

    def test_thread_safety(self):
        ec = EventCollector()
        def producer():
            for i in range(50):
                ec.on_event("step", {"iteration": i})
        t = threading.Thread(target=producer)
        t.start()
        t.join()
        assert len(ec.snapshot()) == 50


class TestFormatEventsNewTools:
    def test_connector_docs_full(self):
        events = [{
            "type": "tool_result",
            "name": "query_connector_docs",
            "result": json.dumps({
                "connector_name": "Jdbc",
                "connector_type": "both",
                "description": "JDBC connector",
                "required_params": [
                    {"name": "url", "type": "string", "description": "JDBC URL", "example": "jdbc:mysql://..."},
                ],
                "optional_params": [],
                "notes": [],
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "Jdbc" in msgs[0]["content"]
        assert "url" in msgs[0]["content"]

    def test_connector_docs_param_detail(self):
        events = [{
            "type": "tool_result",
            "name": "query_connector_docs",
            "result": json.dumps({
                "connector_name": "Kafka",
                "param_detail": {
                    "name": "topic",
                    "type": "string",
                    "required": True,
                    "description": "Kafka topic name",
                    "example": 'topic = "my-topic"',
                },
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "topic" in msgs[0]["content"]
        assert "string" in msgs[0]["content"]

    def test_config_version_list(self):
        events = [{
            "type": "tool_result",
            "name": "list_config_versions",
            "result": json.dumps({
                "config_path": "job.conf",
                "versions": [
                    {"version": 1, "timestamp": "2026-09-12 10:00:00", "size_bytes": 512, "path": "v1.conf"},
                    {"version": 2, "timestamp": "2026-09-12 10:05:00", "size_bytes": 600, "path": "v2.conf"},
                ],
                "count": 2,
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "2 version" in msgs[0]["content"]
        assert "v1" in msgs[0]["content"]

    def test_config_version_empty(self):
        events = [{
            "type": "tool_result",
            "name": "list_config_versions",
            "result": json.dumps({"versions": [], "count": 0, "message": "No version history found"}),
        }]
        msgs = _format_events_as_chat(events)
        assert "No version history" in msgs[0]["content"]

    def test_metrics_in_run_result(self):
        events = [{
            "type": "tool_result",
            "name": "run_seatunnel_job",
            "result": json.dumps({
                "success": True, "exit_code": 0,
                "stdout": "ok", "stderr": "",
                "metrics": {"total_read_count": 100, "total_write_count": 100, "duration_ms": 2500},
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "100" in msgs[0]["content"]
        assert "Metrics" in msgs[0]["content"]

    def test_batch_results(self):
        events = [{
            "type": "tool_result",
            "name": "run_batch",
            "result": json.dumps({
                "total": 2, "executed": 2, "passed": 1, "failed": 1,
                "stopped_early": False,
                "results": [
                    {"index": 1, "config_path": "a.conf", "success": True},
                    {"index": 2, "config_path": "b.conf", "success": False, "error": "not found"},
                ],
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "1/2 passed" in msgs[0]["content"]
        assert "a.conf" in msgs[0]["content"]

    def test_batch_all_pass(self):
        events = [{
            "type": "tool_result",
            "name": "run_batch",
            "result": json.dumps({
                "total": 2, "executed": 2, "passed": 2, "failed": 0,
                "stopped_early": False,
                "results": [
                    {"index": 1, "config_path": "a.conf", "success": True},
                    {"index": 2, "config_path": "b.conf", "success": True},
                ],
            }),
        }]
        msgs = _format_events_as_chat(events)
        content = msgs[0]["content"]
        assert "2/2 passed" in content

    def test_write_config_shows_version(self):
        events = [{
            "type": "tool_result",
            "name": "write_config",
            "result": json.dumps({
                "success": True, "config_path": "job.conf",
                "message": "written", "version": 3,
            }),
        }]
        msgs = _format_events_as_chat(events)
        assert "version 3" in msgs[0]["content"]


class TestElapsedTimeDisplay:
    def test_step_shows_elapsed(self):
        import time as _time
        start = _time.time() - 5.0
        events = [{"type": "step", "iteration": 1, "max": 20, "phase": "thinking"}]
        msgs = _format_events_as_chat(events, start_time=start)
        assert len(msgs) == 1
        assert "s)" in msgs[0]["content"]

    def test_step_no_elapsed_without_start(self):
        events = [{"type": "step", "iteration": 1, "max": 20, "phase": "thinking"}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "s)" not in msgs[0]["content"]


class TestTokenUsageDisplay:
    def test_usage_event_rendered(self):
        events = [{"type": "usage", "input_tokens": 1500, "output_tokens": 300}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 1
        assert "1,500" in msgs[0]["content"]
        assert "300" in msgs[0]["content"]

    def test_usage_event_zero_skipped(self):
        events = [{"type": "usage", "input_tokens": 0, "output_tokens": 0}]
        msgs = _format_events_as_chat(events)
        assert len(msgs) == 0


class TestNewToolEmojis:
    def test_restore_config_emoji(self):
        from seatunnel_agent.agents.data.seatunnel.rendering import _TOOL_EMOJI
        assert "restore_config_version" in _TOOL_EMOJI
        assert "delete_config" in _TOOL_EMOJI
        assert "compare_config_versions" in _TOOL_EMOJI
        assert "explain_config" in _TOOL_EMOJI
