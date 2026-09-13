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


def test_read_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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


def test_run_batch_exception_in_job(monkeypatch):
    """If _run_seatunnel_job raises, batch catches it instead of crashing."""
    from seatunnel_agent import tools as _tools_mod
    def _boom(*a, **kw):
        raise RuntimeError("seatunnel_bin is not set")
    monkeypatch.setattr(_tools_mod, "_run_seatunnel_job", _boom)
    result = json.loads(execute_tool(
        "run_batch",
        {"config_paths": ["a.conf", "b.conf"], "stop_on_failure": False},
        FAKE_SETTINGS,
    ))
    assert result["failed"] == 2
    assert result["executed"] == 2


# --- restore_config_version ---


def test_restore_config_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "v1 content"}, FAKE_SETTINGS)
    execute_tool("write_config", {"config_path": str(config), "content": "v2 content"}, FAKE_SETTINGS)
    assert config.read_text() == "v2 content"
    result = json.loads(execute_tool(
        "restore_config_version",
        {"config_path": str(config), "version": 1},
        FAKE_SETTINGS,
    ))
    assert result["success"] is True
    assert result["version"] >= 1
    assert config.read_text() == "v1 content"


def test_restore_config_version_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "v1"}, FAKE_SETTINGS)
    result = json.loads(execute_tool(
        "restore_config_version",
        {"config_path": str(config), "version": 99},
        FAKE_SETTINGS,
    ))
    assert "error" in result


def test_restore_config_version_no_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(execute_tool(
        "restore_config_version",
        {"config_path": "nonexistent.conf", "version": 1},
        FAKE_SETTINGS,
    ))
    assert "error" in result


# --- delete_config ---


def test_delete_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    config.write_text("content")
    result = json.loads(execute_tool(
        "delete_config",
        {"config_path": str(config)},
        FAKE_SETTINGS,
    ))
    assert result["success"] is True
    assert not config.exists()


def test_delete_config_nonexistent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(execute_tool(
        "delete_config",
        {"config_path": str(tmp_path / "no.conf")},
        FAKE_SETTINGS,
    ))
    assert "error" in result


def test_delete_config_bad_extension(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "bad.txt"
    bad.write_text("x")
    result = json.loads(execute_tool(
        "delete_config",
        {"config_path": str(bad)},
        FAKE_SETTINGS,
    ))
    assert "error" in result


def test_delete_config_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(execute_tool(
        "delete_config",
        {"config_path": "../../../etc/evil.conf"},
        FAKE_SETTINGS,
    ))
    assert "error" in result


# --- compare_config_versions ---


def test_compare_config_versions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "version 1"}, FAKE_SETTINGS)
    execute_tool("write_config", {"config_path": str(config), "content": "version 2"}, FAKE_SETTINGS)
    result = json.loads(execute_tool(
        "compare_config_versions",
        {"config_path": str(config), "version_a": 1, "version_b": 2},
        FAKE_SETTINGS,
    ))
    assert "diff" in result
    assert "version 1" in result["diff"]
    assert "version 2" in result["diff"]


def test_compare_config_versions_same(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "same"}, FAKE_SETTINGS)
    execute_tool("write_config", {"config_path": str(config), "content": "same"}, FAKE_SETTINGS)
    result = json.loads(execute_tool(
        "compare_config_versions",
        {"config_path": str(config), "version_a": 1, "version_b": 2},
        FAKE_SETTINGS,
    ))
    assert result["diff"] == "(no differences)"


def test_compare_config_versions_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    execute_tool("write_config", {"config_path": str(config), "content": "v1"}, FAKE_SETTINGS)
    result = json.loads(execute_tool(
        "compare_config_versions",
        {"config_path": str(config), "version_a": 1, "version_b": 99},
        FAKE_SETTINGS,
    ))
    assert "error" in result


# --- explain_config ---


def test_explain_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "job.conf"
    config.write_text(
        'env { job.mode = "BATCH"\n  parallelism = 2 }\n'
        "source { FakeSource { rows = 10 } }\n"
        "transform {}\n"
        "sink { Console {} }\n"
    )
    result = json.loads(execute_tool(
        "explain_config",
        {"config_path": str(config)},
        FAKE_SETTINGS,
    ))
    assert result["config_path"] == str(config)
    assert result["job_mode"] == "BATCH"
    assert result["parallelism"] == 2
    assert "FakeSource" in str(result.get("source", {}))
    assert "Console" in str(result.get("sink", {}))


def test_explain_config_nonexistent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = json.loads(execute_tool(
        "explain_config",
        {"config_path": "/no/such/config.conf"},
        FAKE_SETTINGS,
    ))
    assert "error" in result


def test_explain_config_invalid_hocon(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "bad.conf"
    config.write_text("this is {{ not valid")
    result = json.loads(execute_tool(
        "explain_config",
        {"config_path": str(config)},
        FAKE_SETTINGS,
    ))
    assert "error" in result


# --- Optimization tests: version collision fix ---


class TestVersionCollisionFix:
    def test_version_after_gap(self, tmp_path, monkeypatch):
        """Deleting a version file should not cause collision."""
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "gap.conf"
        config.write_text("v1")
        execute_tool("write_config", {"config_path": str(config), "content": "v1"}, FAKE_SETTINGS)
        config.write_text("v2")
        execute_tool("write_config", {"config_path": str(config), "content": "v2"}, FAKE_SETTINGS)
        # Delete v1 from history
        history_dir = list((tmp_path / ".config_history").iterdir())[0]
        v1_files = [f for f in history_dir.iterdir() if f.name.startswith("v1_")]
        for f in v1_files:
            f.unlink()
        # Write v3 — should be v3, not v2
        config.write_text("v3")
        result = json.loads(execute_tool(
            "write_config", {"config_path": str(config), "content": "v3"}, FAKE_SETTINGS
        ))
        assert result["version"] >= 3


# --- Optimization tests: _read_config path traversal guard ---


class TestReadConfigPathGuard:
    def test_read_outside_cwd_blocked(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside.conf"
        outside.write_text("env {}")
        try:
            result = json.loads(execute_tool(
                "read_config", {"config_path": str(outside)}, FAKE_SETTINGS
            ))
            assert "error" in result
            assert "outside" in result["error"].lower()
        finally:
            if outside.exists():
                outside.unlink()

    def test_read_inside_cwd_allowed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "ok.conf"
        config.write_text("env {}")
        result = json.loads(execute_tool(
            "read_config", {"config_path": str(config)}, FAKE_SETTINGS
        ))
        assert "content" in result


# --- Optimization tests: _validate_config_path helper ---


class TestValidateConfigPath:
    def test_rejects_bad_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "write_config", {"config_path": "test.txt", "content": "x"}, FAKE_SETTINGS
        ))
        assert "error" in result

    def test_rejects_path_traversal(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "delete_config", {"config_path": "../../../etc/evil.conf"}, FAKE_SETTINGS
        ))
        assert "error" in result


class TestReadConfigExtensionGuard:
    """read_config now uses _validate_config_path and rejects non-config extensions."""

    def test_read_env_file_blocked(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=secret")
        result = json.loads(execute_tool(
            "read_config", {"config_path": str(env_file)}, FAKE_SETTINGS
        ))
        assert "error" in result
        assert "extension" in result["error"].lower()

    def test_read_py_file_blocked(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        py_file = tmp_path / "script.py"
        py_file.write_text("print('hello')")
        result = json.loads(execute_tool(
            "read_config", {"config_path": str(py_file)}, FAKE_SETTINGS
        ))
        assert "error" in result

    def test_read_conf_file_allowed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        conf = tmp_path / "job.conf"
        conf.write_text("env {}")
        result = json.loads(execute_tool(
            "read_config", {"config_path": str(conf)}, FAKE_SETTINGS
        ))
        assert "content" in result


class TestVersionToolsPathValidation:
    """Version-related tools now validate paths before operating."""

    def test_list_versions_rejects_bad_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "list_config_versions", {"config_path": "data.csv"}, FAKE_SETTINGS
        ))
        assert "error" in result

    def test_restore_version_rejects_traversal(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "restore_config_version",
            {"config_path": "../../../etc/evil.conf", "version": 1},
            FAKE_SETTINGS,
        ))
        assert "error" in result

    def test_compare_versions_rejects_bad_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "compare_config_versions",
            {"config_path": "data.txt", "version_a": 1, "version_b": 2},
            FAKE_SETTINGS,
        ))
        assert "error" in result

    def test_explain_config_rejects_bad_extension(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "explain_config", {"config_path": "script.py"}, FAKE_SETTINGS
        ))
        assert "error" in result
