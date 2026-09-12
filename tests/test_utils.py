"""Tests for utility functions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.utils import (
    find_latest_log,
    resolve_log_path,
    safe_json,
    truncate,
)


class TestTruncate:
    def test_short_string_unchanged(self):
        assert truncate("hello", 100) == "hello"

    def test_exact_limit_unchanged(self):
        s = "x" * 50
        assert truncate(s, 50) == s

    def test_long_string_truncated(self):
        s = "x" * 100
        result = truncate(s, 50)
        assert len(result) < 100
        assert result.endswith("... [truncated]")
        assert result.startswith("x" * 50)

    def test_default_limit(self):
        s = "a" * 4000
        result = truncate(s)
        assert "truncated" in result
        assert len(result) < 4000


class TestFindLatestLog:
    def test_no_directory(self):
        assert find_latest_log("/nonexistent/path") is None

    def test_empty_directory(self, tmp_path):
        assert find_latest_log(str(tmp_path)) is None

    def test_single_log(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("log content")
        result = find_latest_log(str(tmp_path))
        assert result == str(log)

    def test_multiple_logs_returns_latest(self, tmp_path):
        import time
        old = tmp_path / "old.log"
        old.write_text("old")
        time.sleep(0.05)
        new = tmp_path / "new.log"
        new.write_text("new")
        result = find_latest_log(str(tmp_path))
        assert result == str(new)

    def test_ignores_non_log_files(self, tmp_path):
        (tmp_path / "data.txt").write_text("not a log")
        assert find_latest_log(str(tmp_path)) is None


class TestSafeJson:
    def test_dict(self):
        result = safe_json({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_unicode(self):
        result = safe_json({"msg": "你好"})
        assert "你好" in result

    def test_unserializable_uses_str(self):
        result = safe_json({"path": Path("/tmp/test")})
        parsed = json.loads(result)
        assert "/tmp/test" in parsed["path"] or "\\tmp\\test" in parsed["path"]


class TestResolveLogPath:
    def test_direct_path(self):
        assert resolve_log_path("/some/file.log", "/st") == "/some/file.log"

    def test_auto_finds_log(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log = log_dir / "seatunnel.log"
        log.write_text("error here")
        result = resolve_log_path("auto", str(tmp_path))
        assert result == str(log)

    def test_auto_no_logs_raises(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            resolve_log_path("auto", str(tmp_path))

    def test_directory_path(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("content")
        result = resolve_log_path(str(tmp_path), "/unused")
        assert result == str(log)

    def test_directory_no_logs_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_log_path(str(tmp_path), "/unused")
