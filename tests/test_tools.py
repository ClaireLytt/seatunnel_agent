from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.config import Settings
from seatunnel_agent.tools import execute_tool, _parse_job_metrics

import tempfile as _tempfile

_tmp = _tempfile.gettempdir()

FAKE_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home=str(Path(_tmp) / "nonexistent-seatunnel"),
    seatunnel_bin=str(Path(_tmp) / "nonexistent-seatunnel" / "bin" / "seatunnel.sh"),
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


def test_write_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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


def test_write_config_creates_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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


def test_write_config_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": "../../../etc/evil.conf", "content": "pwned"},
            FAKE_SETTINGS,
        )
    )
    assert "error" in result
    assert "outside" in result["error"].lower()


def test_write_config_allows_cwd_subdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": "subdir/job.conf", "content": "source {}"},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is True
    assert (tmp_path / "subdir" / "job.conf").exists()


def test_test_connection_unreachable(monkeypatch):
    import socket as _socket
    monkeypatch.setattr(
        _socket, "create_connection",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("Connection refused")),
    )
    result = json.loads(
        execute_tool(
            "test_connection",
            {"host": "192.0.2.1", "port": 1},
            FAKE_SETTINGS,
        )
    )
    assert result["reachable"] is False
    assert "error" in result or "message" in result


def test_test_connection_with_type_label(monkeypatch):
    import socket as _socket
    monkeypatch.setattr(
        _socket, "create_connection",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("Connection refused")),
    )
    result = json.loads(
        execute_tool(
            "test_connection",
            {"host": "192.0.2.1", "port": 1, "service_type": "MySQL"},
            FAKE_SETTINGS,
        )
    )
    assert result["reachable"] is False


def test_write_config_diff_on_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    config.write_text("old content here")
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": str(config), "content": "new content here"},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is True
    assert result["had_changes"] is True
    assert "diff" in result
    assert "old content" in result["diff"]
    assert "new content" in result["diff"]


def test_write_config_no_diff_same_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    config.write_text("same content")
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": str(config), "content": "same content"},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is True
    assert result["had_changes"] is False
    assert "diff" not in result


def test_write_config_no_diff_new_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "brand_new.conf"
    result = json.loads(
        execute_tool(
            "write_config",
            {"config_path": str(config), "content": "new file content"},
            FAKE_SETTINGS,
        )
    )
    assert result["success"] is True
    assert "diff" not in result
    assert "had_changes" not in result


def test_test_connection_reachable(monkeypatch):
    import socket as _socket
    mock_sock = type("MockSocket", (), {"close": lambda self: None})()
    monkeypatch.setattr(
        _socket, "create_connection",
        lambda *a, **kw: mock_sock,
    )
    result = json.loads(
        execute_tool(
            "test_connection",
            {"host": "localhost", "port": 3306, "service_type": "MySQL"},
            FAKE_SETTINGS,
        )
    )
    assert result["reachable"] is True
    assert "latency_ms" in result
    assert "MySQL" in result["message"]


def test_unknown_tool():
    result = json.loads(
        execute_tool("nonexistent_tool", {}, FAKE_SETTINGS)
    )
    assert "error" in result


# --- _parse_job_metrics ---


def test_parse_metrics_read_write_counts():
    stdout = "Total Read Count:       100\nTotal Write Count:      100\n"
    metrics = _parse_job_metrics(stdout, "")
    assert metrics["total_read_count"] == 100
    assert metrics["total_write_count"] == 100


def test_parse_metrics_duration():
    stdout = "Job finished, elapsed: 5000 ms\n"
    metrics = _parse_job_metrics(stdout, "")
    assert metrics["duration_ms"] == 5000


def test_parse_metrics_duration_seconds():
    stdout = "took: 12 seconds\n"
    metrics = _parse_job_metrics(stdout, "")
    assert metrics["duration_ms"] == 12000


def test_parse_metrics_no_metrics():
    assert _parse_job_metrics("hello world", "") is None


def test_parse_metrics_status_finished():
    metrics = _parse_job_metrics("Job FINISHED successfully", "")
    assert metrics["status_summary"] == "FINISHED"


def test_parse_metrics_status_failed():
    metrics = _parse_job_metrics("", "java.lang.Exception: something broke")
    assert metrics["status_summary"] == "FAILED"


def test_parse_metrics_source_received_count():
    metrics = _parse_job_metrics("SourceReceivedCount = 200", "")
    assert metrics["total_read_count"] == 200


def test_parse_metrics_bytes():
    metrics = _parse_job_metrics("Total Read Bytes: 1024\nTotal Write Bytes: 2048", "")
    assert metrics["total_read_bytes"] == 1024
    assert metrics["total_write_bytes"] == 2048


# --- write_config version history ---


def test_write_config_saves_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    result = json.loads(execute_tool(
        "write_config", {"config_path": str(config), "content": "v1 content"}, FAKE_SETTINGS
    ))
    assert result["success"] is True
    assert "version" in result
    assert result["version"] == 1
    history_dir = tmp_path / ".config_history" / "job.conf"
    assert history_dir.is_dir()


def test_write_config_increments_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    r1 = json.loads(execute_tool(
        "write_config", {"config_path": str(config), "content": "v1"}, FAKE_SETTINGS
    ))
    r2 = json.loads(execute_tool(
        "write_config", {"config_path": str(config), "content": "v2"}, FAKE_SETTINGS
    ))
    assert r1["version"] == 1
    assert r2["version"] == 2


# --- list_config_versions ---


def test_list_config_versions_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(execute_tool(
        "list_config_versions", {"config_path": "nonexistent.conf"}, FAKE_SETTINGS
    ))
    assert result["count"] == 0
    assert result["versions"] == []


def test_list_config_versions_with_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "v1"}, FAKE_SETTINGS)
    execute_tool("write_config", {"config_path": str(config), "content": "v2"}, FAKE_SETTINGS)
    result = json.loads(execute_tool(
        "list_config_versions", {"config_path": str(config)}, FAKE_SETTINGS
    ))
    assert result["count"] >= 2
    assert result["versions"][0]["version"] == 1
    assert "timestamp" in result["versions"][0]


def test_list_config_versions_subdir_isolation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    config_a = tmp_path / "a" / "job.conf"
    config_b = tmp_path / "b" / "job.conf"
    execute_tool("write_config", {"config_path": str(config_a), "content": "a"}, FAKE_SETTINGS)
    execute_tool("write_config", {"config_path": str(config_b), "content": "b"}, FAKE_SETTINGS)
    r_a = json.loads(execute_tool(
        "list_config_versions", {"config_path": str(config_a)}, FAKE_SETTINGS
    ))
    r_b = json.loads(execute_tool(
        "list_config_versions", {"config_path": str(config_b)}, FAKE_SETTINGS
    ))
    assert r_a["count"] == 1
    assert r_b["count"] == 1


# --- run_batch ---


def test_run_batch_empty():
    result = json.loads(execute_tool("run_batch", {"config_paths": []}, FAKE_SETTINGS))
    assert "error" in result


def test_run_batch_too_many():
    paths = [f"/fake/config_{i}.conf" for i in range(25)]
    result = json.loads(execute_tool("run_batch", {"config_paths": paths}, FAKE_SETTINGS))
    assert "error" in result


def test_run_batch_stop_on_failure():
    result = json.loads(execute_tool(
        "run_batch",
        {"config_paths": ["/no/such/a.conf", "/no/such/b.conf"]},
        FAKE_SETTINGS,
    ))
    assert result["failed"] >= 1
    assert result["stopped_early"] is True
    assert result["executed"] == 1


def test_run_batch_continue_on_failure():
    result = json.loads(execute_tool(
        "run_batch",
        {"config_paths": ["/no/a.conf", "/no/b.conf"], "stop_on_failure": False},
        FAKE_SETTINGS,
    ))
    assert result["executed"] == 2
    assert result["stopped_early"] is False
    assert result["failed"] == 2
