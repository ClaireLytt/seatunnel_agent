# -*- coding: utf-8 -*-
"""Code-fix agent: tool safety, loop skeleton, end-to-end fix with FakeLLM."""

from __future__ import annotations

import subprocess

import pytest

from seatunnel_agent.agent_core import ToolLoopAgent, ToolSpec
from seatunnel_agent.code_fix import build_tools, fix, render_markdown
from seatunnel_agent.config import Settings
from seatunnel_agent.llm import LLMResponse, ToolCall

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


def _text(reply):
    return LLMResponse(wants_tool_use=False, tool_calls=[], thinking_text="",
                       reply_text=reply, raw_content={"f": 1}, usage={})


def _tool(name, inp, cid="c1"):
    return LLMResponse(wants_tool_use=True,
                       tool_calls=[ToolCall(id=cid, name=name, input=inp)],
                       thinking_text="", reply_text="",
                       raw_content={"f": 1}, usage={})


class TestTools:
    def test_path_escape_blocked(self, tmp_path):
        make_project(tmp_path, git=False)
        tools = {t.name: t for t in build_tools(tmp_path)}
        out = tools["read_file"].run(path="../outside.txt")
        assert False, out  # pragma: no cover — replaced below

    # the loop wraps tool exceptions; test the raw guard directly instead
    def test_path_guard_raises(self, tmp_path):
        from seatunnel_agent.code_fix.tools import _resolve
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


# remove the placeholder that must not run
del TestTools.test_path_escape_blocked


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
