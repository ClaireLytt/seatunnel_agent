from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.config import Settings
from seatunnel_agent.tools import execute_tool

FAKE_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home="/tmp/nonexistent-seatunnel",
    seatunnel_bin="/tmp/nonexistent-seatunnel/bin/seatunnel.sh",
)


# --- validate_config ---


def test_validate_config_valid(tmp_path):
    config = tmp_path / "job.conf"
    config.write_text(
        'env { job.mode = "BATCH" }\n'
        "source { FakeSource { rows = 10 } }\n"
        "transform {}\n"
        "sink { Console {} }\n"
    )
    result = json.loads(
        execute_tool("validate_config", {"config_path": str(config)}, FAKE_SETTINGS)
    )
    assert result["valid"] is True
    assert not result["errors"]
    assert "source" in result["sections_found"]
    assert "sink" in result["sections_found"]


def test_validate_config_missing_source(tmp_path):
    config = tmp_path / "job.conf"
    config.write_text(
        'env { job.mode = "BATCH" }\n'
        "sink { Console {} }\n"
    )
    result = json.loads(
        execute_tool("validate_config", {"config_path": str(config)}, FAKE_SETTINGS)
    )
    assert result["valid"] is False
    assert any("source" in e.lower() for e in result["errors"])


def test_validate_config_missing_sink(tmp_path):
    config = tmp_path / "job.conf"
    config.write_text(
        "source { FakeSource { rows = 10 } }\n"
    )
    result = json.loads(
        execute_tool("validate_config", {"config_path": str(config)}, FAKE_SETTINGS)
    )
    assert result["valid"] is False
    assert any("sink" in e.lower() for e in result["errors"])


def test_validate_config_syntax_error(tmp_path):
    config = tmp_path / "job.conf"
    config.write_text("this is {{ not valid hocon")
    result = json.loads(
        execute_tool("validate_config", {"config_path": str(config)}, FAKE_SETTINGS)
    )
    assert result["valid"] is False
    assert any("syntax" in e.lower() or "error" in e.lower() for e in result["errors"])


def test_validate_config_nonexistent():
    result = json.loads(
        execute_tool("validate_config", {"config_path": "/no/such/file.conf"}, FAKE_SETTINGS)
    )
    assert result["valid"] is False


# --- read_config / write_config ---


def test_read_config(tmp_path):
    config = tmp_path / "job.conf"
    content = 'env { job.mode = "BATCH" }'
    config.write_text(content)
    result = json.loads(
        execute_tool("read_config", {"config_path": str(config)}, FAKE_SETTINGS)
    )
    assert result["content"] == content


def test_read_config_nonexistent():
    result = json.loads(
        execute_tool("read_config", {"config_path": "/no/such/file.conf"}, FAKE_SETTINGS)
    )
    assert "error" in result


def test_write_config(tmp_path):
    config = tmp_path / "new.conf"
    content = 'env { job.mode = "BATCH" }\nsource { FakeSource {} }\nsink { Console {} }'
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": str(config), "content": content},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is True
    assert config.read_text() == content


def test_write_config_creates_backup(tmp_path):
    config = tmp_path / "existing.conf"
    config.write_text("original content")

    execute_tool(
        "write_config",
        {"config_path": str(config), "content": "new content"},
        FAKE_SETTINGS,
    )

    backup = tmp_path / "existing.conf.bak"
    assert backup.exists()
    assert backup.read_text() == "original content"
    assert config.read_text() == "new content"


def test_write_config_rejects_bad_extension(tmp_path):
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": str(tmp_path / "bad.txt"), "content": "stuff"},
            FAKE_SETTINGS,
        )
    )
    assert "error" in result


# --- read_log ---


def test_read_log_tail(tmp_path):
    log_file = tmp_path / "seatunnel.log"
    lines = [f"line {i}" for i in range(200)]
    log_file.write_text("\n".join(lines))
    result = json.loads(
        execute_tool(
            "read_log",
            {"log_path": str(log_file), "tail_lines": 50},
            FAKE_SETTINGS,
        )
    )
    assert result["returned_lines"] == 50
    assert result["total_lines"] == 200


def test_read_log_nonexistent():
    result = json.loads(
        execute_tool("read_log", {"log_path": "/no/such/file.log"}, FAKE_SETTINGS)
    )
    assert "error" in result


# --- run_seatunnel_job ---


def test_run_seatunnel_job_binary_not_found(tmp_path):
    config = tmp_path / "job.conf"
    config.write_text("source { FakeSource {} }\nsink { Console {} }")
    result = json.loads(
        execute_tool(
            "run_seatunnel_job", {"config_path": str(config)}, FAKE_SETTINGS
        )
    )
    assert result["success"] is False
    assert "not found" in result.get("error", "").lower()


def test_run_seatunnel_job_config_not_found():
    result = json.loads(
        execute_tool(
            "run_seatunnel_job",
            {"config_path": "/no/such/config.conf"},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is False


# --- list_connectors ---


def test_list_connectors_fallback():
    result = json.loads(
        execute_tool("list_connectors", {}, FAKE_SETTINGS)
    )
    assert "sources" in result or "installed_connectors" in result
    assert "note" in result


# --- unknown tool ---


def test_unknown_tool():
    result = json.loads(
        execute_tool("nonexistent_tool", {}, FAKE_SETTINGS)
    )
    assert "error" in result
