"""Code-fix agent: tool safety, loop skeleton, end-to-end fix with FakeLLM."""

from __future__ import annotations

import subprocess

import pytest

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.agents.ai.code_fix import build_tools, fix, render_markdown
from seatunnel_agent.common.config import Settings

SETTINGS = Settings(api_key="sk-test")

_BUGGY = '''\
def divide(a, b):
    return a * b  # BUG: should divide
'''

_TEST = '''\
from app import divide


def test_divide():
    assert divide(10, 2) == 5
'''


def make_project(tmp_path, git=True):
    (tmp_path / "app.py").write_text(_BUGGY, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text(_TEST, encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent))\n",
        encoding="utf-8")
    if git:
        for cmd in (["git", "init", "-q"],
                    ["git", "add", "-A"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                     "commit", "-qm", "init"]):
            subprocess.run(cmd, cwd=tmp_path, check=True,
                           capture_output=True)
    return tmp_path


class ScriptedClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, system, messages):
        return self.responses.pop(0) if self.responses else _text("done")

    def append_assistant(self, raw):
        return {"role": "assistant", "content": raw}

    def build_tool_result_message(self, trs):
        return {"role": "user", "content": trs}


from tests.conftest import llm_text as _text
from tests.conftest import llm_tool as _tool


class TestTools:
    # the loop wraps tool exceptions; test the raw guard directly
    def test_path_guard_raises(self, tmp_path):
        from seatunnel_agent.agents.ai.code_fix.tools import _resolve
        make_project(tmp_path, git=False)
        with pytest.raises(ValueError):
            _resolve(tmp_path, "../outside.txt")
        with pytest.raises(ValueError):
            _resolve(tmp_path, ".git/config")

    def test_apply_patch_requires_unique(self, tmp_path):
        make_project(tmp_path, git=False)
        tools = {t.name: t for t in build_tools(tmp_path)}
        assert "not found" in tools["apply_patch"].run(
            path="app.py", old="nope", new="x")
        (tmp_path / "dup.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
        assert "2 times" in tools["apply_patch"].run(
            path="dup.py", old="x = 1", new="y = 1")

    def test_run_tests_red_then_green(self, tmp_path):
        make_project(tmp_path, git=False)
        tools = {t.name: t for t in build_tools(tmp_path)}
        assert tools["run_tests"].run().startswith("[EXIT")
        tools["apply_patch"].run(path="app.py", old="a * b", new="a / b")
        assert tools["run_tests"].run().startswith("[GREEN]")


class TestLoopSkeleton:
    def test_unknown_tool_and_error_isolation(self):
        noisy = ToolSpec("boom", "x", {"type": "object", "properties": {},
                                       "required": []},
                         lambda: (_ for _ in ()).throw(RuntimeError("k")))
        agent = ToolLoopAgent(SETTINGS, [noisy], "sys", "t",
                              client=ScriptedClient([
                                  _tool("nope", {}), _tool("boom", {}),
                                  _text("ok")]))
        result = agent.run("go")
        assert result.steps[0].error and "unknown tool" in result.steps[0].output
        assert result.steps[1].error and "kaput" not in result.steps[1].output
        assert result.reply == "ok"

    def test_step_limit_forces_summary(self):
        spec = ToolSpec("t", "x", {"type": "object", "properties": {},
                                   "required": []}, lambda: "r")
        client = ScriptedClient([_tool("t", {}, f"c{i}") for i in range(2)]
                                + [_text("partial")])
        agent = ToolLoopAgent(SETTINGS, [spec], "sys", "t",
                              max_steps=2, client=client)
        result = agent.run("go")
        assert result.truncated and result.reply == "partial"


class TestEndToEnd:
    def _script(self):
        return ScriptedClient([
            _tool("run_tests", {}),
            _tool("read_file", {"path": "app.py"}),
            _tool("apply_patch", {"path": "app.py", "old": "a * b",
                                  "new": "a / b"}),
            _tool("run_tests", {}),
            _text("修好了:乘法应为除法。"),
        ])

    def test_fix_in_worktree_leaves_repo_untouched(self, tmp_path):
        repo = make_project(tmp_path)
        result = fix(repo, SETTINGS, client=self._script())
        assert result.success, result.final_test_output
        assert "a / b" in result.diff and "a * b" in result.diff
        # the original checkout still carries the bug
        assert "a * b" in (repo / "app.py").read_text(encoding="utf-8")
        assert result.workdir != str(repo)
        md = render_markdown(result, "zh")
        assert "测试已通过" in md and "```diff" in md

    def test_in_place_edits_target(self, tmp_path):
        proj = make_project(tmp_path, git=False)
        result = fix(proj, SETTINGS, in_place=True, client=self._script())
        assert result.success
        assert "a / b" in (proj / "app.py").read_text(encoding="utf-8")

    def test_non_git_requires_in_place(self, tmp_path):
        proj = make_project(tmp_path, git=False)
        with pytest.raises(ValueError, match="in_place"):
            fix(proj, SETTINGS, client=self._script())

    def test_model_claim_not_trusted(self, tmp_path):
        """The model says done without fixing: final run decides."""
        proj = make_project(tmp_path, git=False)
        result = fix(proj, SETTINGS, in_place=True,
                     client=ScriptedClient([_text("都修好了(并没有)")]))
        assert not result.success
        assert result.final_test_output.startswith("[EXIT")


class TestApi:
    """SSE run endpoint backing the React page (ticket 01) — gated by a
    mandatory CODEFIX_API_ALLOWED_DIRS whitelist."""

    def _client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from seatunnel_agent.agents.ai.code_fix.api import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def _events(resp):
        import json as _json
        out = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                out.append(_json.loads(line[len("data: "):]))
        return out

    def test_no_whitelist_403(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CODEFIX_API_ALLOWED_DIRS", raising=False)
        resp = self._client().post("/api/codefix/run",
                                   json={"path": str(tmp_path)})
        assert resp.status_code == 403

    def test_path_outside_whitelist_403(self, tmp_path, monkeypatch):
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setenv("CODEFIX_API_ALLOWED_DIRS", str(allowed))
        resp = self._client().post("/api/codefix/run",
                                   json={"path": str(outside)})
        assert resp.status_code == 403

    def test_run_streams_steps_then_done(self, tmp_path, monkeypatch):
        repo = make_project(tmp_path / "proj" if False else tmp_path)
        monkeypatch.setenv("CODEFIX_API_ALLOWED_DIRS", str(tmp_path))
        monkeypatch.setenv("API_KEY", "sk-test")

        script = ScriptedClient([
            _tool("run_tests", {}),
            _tool("read_file", {"path": "app.py"}),
            _tool("apply_patch", {"path": "app.py", "old": "a * b",
                                  "new": "a / b"}),
            _tool("run_tests", {}),
            _text("fixed"),
        ])
        monkeypatch.setattr("seatunnel_agent.common.llm.LLMClient",
                            lambda *a, **k: script)
        with self._client().stream(
                "POST", "/api/codefix/run",
                json={"path": str(repo), "lang": "en",
                      "max_steps": 8}) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith(
                "text/event-stream")
            events = self._events(resp)
        steps = [e for e in events if e["type"] == "step"]
        assert steps and steps[0]["tool"] == "run_tests"
        done = events[-1]
        assert done["type"] == "done"
        assert done["success"] is True
        assert "a / b" in done["diff"]
        # the original checkout stays untouched (worktree isolation)
        assert "a * b" in (repo / "app.py").read_text(encoding="utf-8")

    def test_no_key_degrades_to_error_event(self, tmp_path, monkeypatch):
        repo = make_project(tmp_path)
        monkeypatch.setenv("CODEFIX_API_ALLOWED_DIRS", str(tmp_path))
        for var in ("API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        monkeypatch.setattr("seatunnel_agent.common.config.load_dotenv",
                            lambda *a, **k: None)
        monkeypatch.setattr(
            "seatunnel_agent.common.settings_store.apply_to_env",
            lambda: None)
        with self._client().stream(
                "POST", "/api/codefix/run",
                json={"path": str(repo), "lang": "en"}) as resp:
            assert resp.status_code == 200
            events = self._events(resp)
        assert events[-1]["type"] == "error"
        assert "key" in events[-1]["message"].lower() \
            or "LLM" in events[-1]["message"]
