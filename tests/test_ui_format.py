"""Tests for UI event formatting and export."""

from __future__ import annotations

import json
import threading
import time
import zipfile
from pathlib import Path

from seatunnel_agent.config import Settings
from seatunnel_agent.ui import (
    EventCollector,
    _build_template_choices,
    _export_session,
    _format_events_as_chat,
    _normalize_chat,
    _template_to_prompt,
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


class TestExportSession:
    def test_export_generates_zip(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        path = _export_session(history, "test123")
        assert path is not None
        assert Path(path).exists()
        with zipfile.ZipFile(path) as zf:
            assert "report.md" in zf.namelist()
            content = zf.read("report.md").decode()
            assert "Hello" in content
            assert "Hi there" in content
            assert "test123" in content
        Path(path).unlink()

    def test_export_includes_config_files(self, tmp_path):
        conf = tmp_path / "job.conf"
        conf.write_text('source { FakeSource {} }\nsink { Console {} }')
        history = [
            {"role": "user", "content": "Create a pipeline"},
            {"role": "assistant", "content": "Done"},
        ]
        path = _export_session(history, "sid1", created_configs=[str(conf)])
        assert path is not None
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert "configs/job.conf" in names
            assert "FakeSource" in zf.read("configs/job.conf").decode()
            report = zf.read("report.md").decode()
            assert "job.conf" in report
        Path(path).unlink()

    def test_export_empty_history(self):
        assert _export_session([], "x") is None


class TestNormalizeChat:
    def test_plain_dicts_unchanged(self):
        history = [{"role": "user", "content": "hello"}]
        result = _normalize_chat(history)
        assert result == [{"role": "user", "content": "hello"}]

    def test_unwraps_single_nested_textmsg(self):
        history = [{"role": "user", "content": "{'text': 'actual text', 'type': 'text'}"}]
        result = _normalize_chat(history)
        assert result[0]["content"] == "actual text"

    def test_unwraps_double_nested_textmsg(self):
        inner = "{'text': 'deep content', 'type': 'text'}"
        outer = "{'text': \"" + inner + "\", 'type': 'text'}"
        history = [{"role": "assistant", "content": outer}]
        result = _normalize_chat(history)
        assert result[0]["content"] == "deep content"

    def test_dict_content_list(self):
        history = [{"role": "user", "content": [{"text": "from dict", "type": "text"}]}]
        result = _normalize_chat(history)
        assert result[0]["content"] == "from dict"

    def test_chatmessage_objects(self):
        from unittest.mock import MagicMock
        msg = MagicMock()
        msg.role = "assistant"
        tm = MagicMock()
        tm.text = "response text"
        msg.content = [tm]
        result = _normalize_chat([msg])
        assert result[0]["content"] == "response text"

    def test_content_with_newlines(self):
        text = "line1\nline2\nline3"
        wrapped = str({"text": text, "type": "text"})
        history = [{"role": "assistant", "content": wrapped}]
        result = _normalize_chat(history)
        assert result[0]["content"] == text

    def test_export_unwraps_textmsg_in_report(self):
        history = [
            {"role": "user", "content": "{'text': 'my question', 'type': 'text'}"},
            {"role": "assistant", "content": "{'text': 'my answer', 'type': 'text'}"},
        ]
        path = _export_session(history, "unwrap-test")
        assert path is not None
        with zipfile.ZipFile(path) as zf:
            report = zf.read("report.md").decode()
            assert "my question" in report
            assert "my answer" in report
            assert "{'text':" not in report
        Path(path).unlink()


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


class TestExportWithSettings:
    def test_report_includes_model_and_provider(self):
        settings = Settings(
            api_key="sk-test",
            model_name="deepseek-chat",
            llm_provider="openai",
        )
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        path = _export_session(history, "settings-test", settings=settings)
        assert path is not None
        with zipfile.ZipFile(path) as zf:
            report = zf.read("report.md").decode()
            assert "deepseek-chat" in report
            assert "openai" in report
        Path(path).unlink()


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


class TestTemplateHelpers:
    def test_build_template_choices_en(self):
        choices = _build_template_choices("en")
        assert len(choices) >= 7
        assert choices[0][1] == ""
        names = [c[1] for c in choices]
        assert "fake_to_console" in names

    def test_build_template_choices_zh(self):
        choices = _build_template_choices("zh")
        assert len(choices) >= 7

    def test_template_to_prompt_en(self):
        result = _template_to_prompt("fake_to_console", "en")
        assert "fake_to_console" in result
        assert "template" in result.lower()

    def test_template_to_prompt_zh(self):
        result = _template_to_prompt("fake_to_console", "zh")
        assert "fake_to_console" in result
        assert "模板" in result

    def test_template_to_prompt_empty_name(self):
        assert _template_to_prompt("", "en") == ""

    def test_template_to_prompt_nonexistent(self):
        assert _template_to_prompt("no_such", "en") == ""
