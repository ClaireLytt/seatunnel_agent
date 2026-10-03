# -*- coding: utf-8 -*-
"""Code-fix agent — run tests, read, patch, re-run, until green.

The full perceive→act→observe loop: the environment (pytest output) drives
every next decision.  Safety model:

* by default work happens in a **fresh git worktree** of the target repo —
  the checkout you point it at is never touched;
* success is decided by a final deterministic test run, never by the
  model's own claim;
* the result carries the ``git diff`` for human review — the agent never
  commits, let alone pushes.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agent_core import Step, ToolLoopAgent
from ..config import Settings
from .tools import build_tools, run_pytest

_SYSTEM = """\
You are a code-fix agent. The user gives you a project whose tests fail;
make them pass with the smallest reasonable change.

Workflow:
1. run_tests to see the failure.
2. read_file around the failing code (list_files if you must locate it).
3. apply_patch with an EXACT unique snippet of the current content.
4. run_tests again. Repeat until [GREEN].

Rules:
- Fix the code under test, not the tests — do not modify files under
  tests/ unless the user explicitly says the test itself is wrong.
- Smallest change that makes the suite pass; no drive-by refactoring.
- apply_patch old= must be copied verbatim from read_file output
  (without the line-number prefixes).
- When the run is [GREEN], stop and summarize what was wrong and what you
  changed, in the user's language.
"""


def _git(workdir: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(workdir), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout


@dataclass
class CodeFixResult:
    success: bool
    reply: str
    steps: list[Step] = field(default_factory=list)
    diff: str = ""
    workdir: str = ""
    final_test_output: str = ""
    truncated: bool = False
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "reply": self.reply,
                "steps": [s.to_dict() for s in self.steps],
                "diff": self.diff, "workdir": self.workdir,
                "final_test_output": self.final_test_output,
                "truncated": self.truncated, "elapsed_ms": self.elapsed_ms}


def fix(path: str | Path,
        settings: Settings,
        tests: str = "",
        instruction: str = "",
        max_steps: int = 12,
        in_place: bool = False,
        client: Any = None,
        on_step=None) -> CodeFixResult:
    """Run the agent against *path*.

    Default: a temporary git worktree of HEAD is created and edited, the
    original checkout stays untouched.  ``in_place=True`` edits *path*
    directly — only for throwaway dirs (it is also the non-git fallback,
    requested explicitly)."""
    start = time.time()
    repo = Path(path).resolve()
    if not repo.is_dir():
        raise ValueError(f"not a directory: {repo}")

    workdir = repo
    worktree_created = False
    if not in_place:
        try:
            _git(repo, "rev-parse", "--git-dir")
        except (RuntimeError, FileNotFoundError):
            raise ValueError(
                "目标不是 git 仓库 — 代码会被直接修改,请显式使用 in_place "
                "(CLI: --in-place) 确认你接受这一点")
        workdir = Path(tempfile.mkdtemp(prefix="codefix_")) / "wt"
        _git(repo, "worktree", "add", "--detach", str(workdir), "HEAD")
        worktree_created = True

    try:
        request = (instruction or "请让测试通过。").strip()
        if tests:
            request += f"\n测试选择器: {tests}"
        agent = ToolLoopAgent(settings, tools=build_tools(workdir),
                              system_prompt=_SYSTEM, agent_name="code_fix",
                              max_steps=max_steps, client=client)
        loop = agent.run(request, on_step=on_step)

        # never trust the model's claim — verify with a deterministic run
        final = run_pytest(workdir, tests)
        success = final.startswith("[GREEN]")
        diff = ""
        try:
            diff = _git(workdir, "diff")
        except (RuntimeError, FileNotFoundError):
            pass
        return CodeFixResult(
            success=success, reply=loop.reply, steps=loop.steps, diff=diff,
            workdir=str(workdir), final_test_output=final,
            truncated=loop.truncated,
            elapsed_ms=int((time.time() - start) * 1000))
    finally:
        # the worktree is kept on disk for inspection; unregister it from
        # the repo so it never blocks future worktree commands
        if worktree_created:
            subprocess.run(["git", "-C", str(repo), "worktree", "prune"],
                           capture_output=True, timeout=30)
