"""Tests for the SeaTunnel REST API client and API-based tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from seatunnel_agent.config import Settings
from seatunnel_agent.tools import execute_tool
from seatunnel_agent.seatunnel_api import SeaTunnelAPI, SeaTunnelAPIConfig


# ---------------------------------------------------------------------------
# Settings fixture with no API URL configured
# ---------------------------------------------------------------------------

_SETTINGS_NO_API = Settings(api_key="test", seatunnel_api_url="")


# ---------------------------------------------------------------------------
# Tool tests: no API URL configured => graceful error
# ---------------------------------------------------------------------------


class TestSeaTunnelAPIToolsNoURL:
    def test_submit_job_no_url(self):
        result = execute_tool("submit_job_api", {"config_path": "test.conf"}, _SETTINGS_NO_API)
        assert "not configured" in result

    def test_get_job_status_no_url(self):
        result = execute_tool("get_job_status", {"job_id": "123"}, _SETTINGS_NO_API)
        assert "not configured" in result

    def test_list_jobs_no_url(self):
        result = execute_tool("list_jobs", {}, _SETTINGS_NO_API)
        assert "not configured" in result

    def test_cancel_job_no_url(self):
        result = execute_tool("cancel_job", {"job_id": "123"}, _SETTINGS_NO_API)
        assert "not configured" in result


# ---------------------------------------------------------------------------
# API client tests with mocked HTTP
# ---------------------------------------------------------------------------


class TestSeaTunnelAPIClient:
    def test_api_connectivity_mock(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"version": "2.3.0"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            ok, msg = api.test_connectivity()
            assert ok
            assert "connected" in msg.lower()

    def test_api_unreachable(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:59999", timeout_s=2))
        ok, msg = api.test_connectivity()
        assert not ok

    def test_submit_job_mock(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"jobId": "12345"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = api.submit_job('{"env": {}}', job_name="test-job")
            assert result["jobId"] == "12345"

    def test_get_job_info_mock(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"jobId": "123", "jobStatus": "RUNNING"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = api.get_job_info("123")
            assert result["jobStatus"] == "RUNNING"

    def test_list_jobs_mock(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'[{"jobId": "1"}, {"jobId": "2"}]'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = api.list_jobs()
            assert len(result) == 2

    def test_list_all_jobs_non_list_returns_empty(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = api.list_all_jobs()
            assert result == []

    def test_cancel_job_mock(self):
        api = SeaTunnelAPI(SeaTunnelAPIConfig("http://localhost:5801"))
        with patch("seatunnel_agent.seatunnel_api.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"jobId": "123", "jobStatus": "CANCELED"}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = api.cancel_job("123")
            assert result["jobStatus"] == "CANCELED"


# ---------------------------------------------------------------------------
# Tool tests: file not found
# ---------------------------------------------------------------------------


class TestSeaTunnelAPIToolsWithURL:
    _SETTINGS = Settings(api_key="test", seatunnel_api_url="http://localhost:5801")

    def test_submit_job_file_not_found(self):
        result = json.loads(
            execute_tool("submit_job_api", {"config_path": "/nonexistent/path.conf"}, self._SETTINGS)
        )
        assert "error" in result
        assert "not found" in result["error"].lower()
