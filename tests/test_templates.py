"""Tests for pipeline template library."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.config import Settings
from seatunnel_agent.templates import (
    TEMPLATES, get_template, list_templates, render_template,
)
from seatunnel_agent.tools import execute_tool

import tempfile as _tempfile

_tmp = _tempfile.gettempdir()

FAKE_SETTINGS = Settings(
    api_key="sk-test",
    seatunnel_home=str(Path(_tmp) / "nonexistent-seatunnel"),
    seatunnel_bin=str(Path(_tmp) / "nonexistent-seatunnel" / "bin" / "seatunnel.sh"),
)


class TestTemplateRegistry:
    def test_has_templates(self):
        assert len(TEMPLATES) >= 6

    def test_get_existing(self):
        t = get_template("fake_to_console")
        assert t is not None
        assert t.name == "fake_to_console"
        assert t.category == "testing"

    def test_get_nonexistent(self):
        assert get_template("no_such_template") is None

    def test_list_all(self):
        all_t = list_templates()
        assert len(all_t) == len(TEMPLATES)

    def test_list_by_category(self):
        db = list_templates("database")
        assert all(t.category == "database" for t in db)
        assert len(db) >= 2

    def test_list_empty_category(self):
        result = list_templates("nonexistent")
        assert result == []


class TestRenderTemplate:
    def test_render_with_defaults(self):
        content = render_template("fake_to_console", {})
        assert content is not None
        assert "FakeSource" in content
        assert "Console" in content

    def test_render_with_custom_params(self):
        content = render_template("fake_to_console", {"rows": "42", "parallelism": "4"})
        assert "rows = 42" in content
        assert "parallelism = 4" in content

    def test_render_nonexistent(self):
        assert render_template("no_such", {}) is None

    def test_render_mysql_template(self):
        content = render_template("mysql_to_console", {
            "hostname": "db.example.com",
            "database": "mydb",
            "table": "users",
        })
        assert "db.example.com" in content
        assert "mydb" in content
        assert "MySQL-CDC" in content


class TestTemplateTools:
    def test_list_templates_tool(self):
        result = json.loads(execute_tool("list_templates", {}, FAKE_SETTINGS))
        assert "templates" in result
        assert result["count"] >= 6
        assert result["templates"][0]["name"] == "fake_to_console"

    def test_list_templates_filtered(self):
        result = json.loads(execute_tool("list_templates", {"category": "streaming"}, FAKE_SETTINGS))
        assert all(t["category"] == "streaming" for t in result["templates"])

    def test_use_template_tool(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "use_template",
            {
                "template_name": "fake_to_console",
                "parameters": {"rows": "20"},
                "config_path": str(tmp_path / "gen.conf"),
            },
            FAKE_SETTINGS,
        ))
        assert result["success"] is True
        content = (tmp_path / "gen.conf").read_text()
        assert "rows = 20" in content

    def test_use_template_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = json.loads(execute_tool(
            "use_template",
            {
                "template_name": "nonexistent",
                "parameters": {},
                "config_path": str(tmp_path / "out.conf"),
            },
            FAKE_SETTINGS,
        ))
        assert "error" in result
