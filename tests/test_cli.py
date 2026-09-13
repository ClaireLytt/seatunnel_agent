"""Tests for CLI entry points."""

from __future__ import annotations

from click.testing import CliRunner

from seatunnel_agent.cli import cli


runner = CliRunner()


class TestCliBasics:
    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "SeaTunnel" in result.output

    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0

    def test_run_missing_args(self):
        result = runner.invoke(cli, ["run"])
        assert result.exit_code != 0

    def test_validate_help(self):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_diagnose_help(self):
        result = runner.invoke(cli, ["diagnose", "--help"])
        assert result.exit_code == 0
        assert "log" in result.output.lower()

    def test_chat_help(self):
        result = runner.invoke(cli, ["chat", "--help"])
        assert result.exit_code == 0

    def test_ui_help(self):
        result = runner.invoke(cli, ["ui", "--help"])
        assert result.exit_code == 0
        assert "port" in result.output.lower()
        assert "host" in result.output.lower()
        assert "share" in result.output.lower()

    def test_chat_list_sessions(self):
        result = runner.invoke(cli, ["chat", "--list-sessions"])
        assert result.exit_code == 0

    def test_batch_help(self):
        result = runner.invoke(cli, ["batch", "--help"])
        assert result.exit_code == 0
        assert "configs" in result.output.lower()
