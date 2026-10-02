# -*- coding: utf-8 -*-
"""Release-notes helper: parsing, bump logic, rendering, polish, CLI, API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seatunnel_agent.cli import cli
from seatunnel_agent.llm import LLMResponse
from seatunnel_agent.release_notes import (
    build_notes,
    next_semver,
    parse_commit_lines,
    polish_markdown,
    render_markdown,
    suggest_bump,
)

DEMO = Path(__file__).resolve().parents[1] / "examples" / "release_demo"
LOG = (DEMO / "commits.txt").read_text(encoding="utf-8")


class TestParsing:
    def test_conventional_fields(self):
        commits = parse_commit_lines("abc1234\tfeat(hub)!: new landing")
        c = commits[0]
        assert (c.sha, c.ctype, c.scope, c.breaking) == \
            ("abc1234", "feat", "hub", True)
        assert c.subject == "new landing"

    def test_aliases_and_other(self):
        assert parse_commit_lines("a\tci: speed up")[0].ctype == "chore"
        assert parse_commit_lines("a\tstyle: fmt")[0].ctype == "refactor"
        assert parse_commit_lines("a\tupdate web link")[0].ctype == "other"

    def test_bare_subject_without_sha(self):
        c = parse_commit_lines("fix: oops")[0]
        assert c.sha == "" and c.ctype == "fix"

    def test_breaking_change_keyword(self):
        c = parse_commit_lines("a\tfeat: drop api BREAKING CHANGE")[0]
        assert c.breaking

    def test_blank_lines_skipped(self):
        assert len(parse_commit_lines("\n\na\tfix: x\n\n")) == 1


class TestBump:
    @pytest.mark.parametrize("log,bump", [
        ("a\tfeat!: drop", "major"),
        ("a\tfeat: add\nb\tfix: oops", "minor"),
        ("a\tfix: oops\nb\tchore: tidy", "patch"),
    ])
    def test_suggest(self, log, bump):
        assert suggest_bump(parse_commit_lines(log)) == bump

    @pytest.mark.parametrize("cur,bump,expect", [
        ("0.2.0", "major", "1.0.0"),
        ("v1.2.3", "minor", "1.3.0"),
        ("1.2.3", "patch", "1.2.4"),
        ("", "minor", "0.1.0"),
        ("2", "patch", "2.0.1"),
    ])
    def test_next_semver(self, cur, bump, expect):
        assert next_semver(cur, bump) == expect


class TestNotes:
    def test_demo_grouping(self):
        notes = build_notes(LOG, "0.2.0")
        assert notes.bump == "major" and notes.next_version == "1.0.0"
        groups = dict((k, [c.sha for c in cs])
                      for k, _label, cs in notes.grouped())
        assert len(groups["feat"]) == 3
        assert "other" in groups  # "update web link"
        assert [c.sha for c in notes.breaking] == ["d4e5f6a"]

    def test_markdown_bilingual(self):
        notes = build_notes(LOG, "0.2.0")
        zh = render_markdown(notes, "zh")
        en = render_markdown(notes, "en")
        assert "发布说明" in zh and "破坏性变更" in zh and "1.0.0" in zh
        assert "Release Notes" in en and "Breaking Changes" in en

    def test_empty_log(self):
        assert "没有提交" in render_markdown(build_notes(""), "zh")


class TestPolish:
    def test_polish_uses_llm(self):
        def factory(_settings):
            class C:
                def chat(self, system, messages):
                    return LLMResponse(wants_tool_use=False, tool_calls=[],
                                       thinking_text="",
                                       reply_text="POLISHED",
                                       raw_content=None, usage={})
            return C()
        assert polish_markdown("raw", "zh", client_factory=factory) \
            == "POLISHED"

    def test_polish_failure_falls_back(self):
        def factory(_settings):
            raise RuntimeError("no key")
        out = polish_markdown("raw md", "zh", client_factory=factory)
        assert "润色失败" in out and "raw md" in out


class TestCli:
    def test_log_file_markdown(self):
        r = CliRunner().invoke(cli, [
            "relnotes", "--log-file", str(DEMO / "commits.txt"),
            "-V", "0.2.0"])
        assert r.exit_code == 0, r.output
        assert "建议版本" in r.output and "1.0.0" in r.output

    def test_log_file_json(self):
        r = CliRunner().invoke(cli, [
            "relnotes", "--log-file", str(DEMO / "commits.txt"),
            "-V", "0.2.0", "-F", "json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.output)
        assert payload["next_version"] == "1.0.0"
        assert payload["breaking"][0]["sha"] == "d4e5f6a"

    def test_real_repo_smoke(self):
        # the project repo itself: git log since full history is fine
        r = CliRunner().invoke(cli, ["relnotes", "--repo", ".",
                                     "--from", "HEAD~3"])
        assert r.exit_code == 0, r.output


class TestApi:
    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.release_notes.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_notes_endpoint(self):
        resp = self._client().post("/api/release/notes", json={
            "log_text": LOG, "current_version": "0.2.0",
            "lang": "en", "report": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["next_version"] == "1.0.0"
        assert "Release Notes" in data["report"]

    def test_health(self):
        resp = self._client().get("/api/release/health")
        assert resp.json() == {"status": "ok", "agent": "release_notes"}
