# -*- coding: utf-8 -*-
"""Dependency health: parsing, checks with an injected resolver, CLI, API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.dep_check import (
    check,
    check_fail,
    collect_from_path,
    parse_pyproject_text,
    parse_requirements_text,
    render_markdown,
)

DEMO = Path(__file__).resolve().parents[1] / "examples" / "depcheck_demo"

_PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"
dependencies = ["click>=8.1", "rich"]

[project.optional-dependencies]
ui = ["gradio>=6.0"]
"""


def fake_resolver(installed: dict[str, tuple[str, str]]):
    return lambda name: installed.get(name)


class TestParsing:
    def test_pyproject_deps_and_extras(self):
        reqs = parse_pyproject_text(_PYPROJECT)
        by = {(r.name, r.group): r.spec for r in reqs}
        assert by[("click", "project")] == ">=8.1"
        assert by[("rich", "project")] == ""
        assert by[("gradio", "extra:ui")] == ">=6.0"

    def test_requirements_text(self):
        reqs = parse_requirements_text(
            "# comment\nClick >= 8.1\n-r other.txt\nPyYAML[safe]==6.0\n")
        assert [(r.name, r.spec) for r in reqs] == \
            [("click", ">= 8.1"), ("pyyaml", "==6.0")]

    def test_malformed_pyproject_raises(self):
        with pytest.raises(ValueError):
            parse_pyproject_text("[project\n")


class TestCheck:
    def test_missing_violated_unpinned_conflict(self):
        reqs = parse_requirements_text(
            "a-pkg>=2.0\nb-pkg\nc-pkg>=1.0\nc-pkg>=9.9\nd-pkg==1.0\n")
        resolver = fake_resolver({
            "a-pkg": ("1.0", "MIT"),        # violates >=2.0
            "b-pkg": ("3.3", "MIT"),        # unpinned
            "c-pkg": ("1.5", "MIT"),        # conflict + violates >=9.9
            # d-pkg missing entirely
        })
        report = check(reqs, resolver=resolver)
        cats = {(f.category, f.package) for f in report.findings}
        assert ("violated", "a-pkg") in cats
        assert ("unpinned", "b-pkg") in cats
        assert ("conflict", "c-pkg") in cats
        assert ("missing", "d-pkg") in cats
        assert report.severities["high"] >= 3

    def test_license_flags(self):
        reqs = parse_requirements_text("x==1.0\ny==1.0\nz==1.0\n")
        resolver = fake_resolver({
            "x": ("1.0", "GPL-3.0-only"),
            "y": ("1.0", ""),
            "z": ("1.0", "MIT"),
        })
        report = check(reqs, resolver=resolver)
        cats = {(f.category, f.package) for f in report.findings}
        assert ("copyleft", "x") in cats
        assert ("unknown_license", "y") in cats
        assert all(p != "z" for c, p in cats)

    def test_clean_report(self):
        reqs = parse_requirements_text("ok-pkg==1.0\n")
        report = check(reqs, resolver=fake_resolver({"ok-pkg": ("1.0", "MIT")}))
        assert report.findings == []
        assert not check_fail(report, "medium")

    def test_fail_ladder(self):
        reqs = parse_requirements_text("b-pkg\n")
        report = check(reqs, resolver=fake_resolver({"b-pkg": ("1.0", "MIT")}))
        assert check_fail(report, "medium")
        assert not check_fail(report, "high")

    def test_real_environment_smoke(self):
        """click really is installed — the default resolver works."""
        reqs = parse_requirements_text("click>=8.0\n")
        report = check(reqs)
        assert not any(f.category == "missing" for f in report.findings)
        assert report.packages[0]["installed"] != "—"


class TestCollect:
    def test_demo_dir(self):
        reqs = collect_from_path(DEMO)
        names = [r.name for r in reqs]
        assert "totally-absent-pkg" in names
        assert names.count("click") == 2


class TestReport:
    def test_markdown_bilingual(self):
        report = check(collect_from_path(DEMO))
        zh = render_markdown(report, "zh")
        en = render_markdown(report, "en")
        assert "依赖体检" in zh and "依赖清单" in zh
        assert "Dependency Health" in en and "Inventory" in en
        assert "totally-absent-pkg" in zh


class TestCli:
    def test_demo_fail_on_high(self):
        r = CliRunner().invoke(cli, ["depcheck", "--path", str(DEMO),
                                     "--fail-on", "high"])
        assert r.exit_code == 1
        assert "依赖体检" in r.output

    def test_json(self):
        r = CliRunner().invoke(cli, ["depcheck", "--path", str(DEMO),
                                     "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["severities"]["high"] >= 1

    def test_empty_dir_exit_2(self, tmp_path):
        r = CliRunner().invoke(cli, ["depcheck", "--path", str(tmp_path)])
        assert r.exit_code == 2


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.dep_check.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_check_endpoint(self):
        resp = self._client().post("/api/depcheck/check", json={
            "requirements_text": "click>=8.1\nsome-absent-thing==1.0\n",
            "lang": "en", "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert any(f["category"] == "missing"
                   for f in data["result"]["findings"])
        assert "Dependency Health" in data["report"]

    def test_requires_input_400(self):
        resp = self._client().post("/api/depcheck/check", json={})
        assert resp.status_code == 400

    def test_health(self):
        resp = self._client().get("/api/depcheck/health")
        assert resp.json() == {"status": "ok", "agent": "dep_check"}
