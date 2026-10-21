"""scripts/cleanup_worktrees.py — the ONLY sanctioned worktree-cleanup
entry point. Codifies the 2026-10-22 incident rules (CLAUDE.md §9):
resolved full-prefix whitelist (never substring matching), one
``git worktree remove`` per path, loud failure with NO deletion
fallback, dry-run by default.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cleanup_worktrees.py"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(tmp_path: Path, name: str = "mainrepo-agent") -> Path:
    """A real git repo whose own path contains 'agent' — the incident's
    trigger shape."""
    repo = tmp_path / name
    repo.mkdir()
    (repo / "a.txt").write_text("x", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "add", "a.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "init")
    return repo


def add_worktree(repo: Path, rel: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--detach", str(path), "HEAD")
    return path


def run_script(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        cwd=repo, capture_output=True, text=True)


class TestWhitelist:
    def test_main_repo_with_agent_in_path_never_selected(self, tmp_path):
        """The incident scenario: the main repo's own path contains
        'agent' — it must never appear in the removal list."""
        repo = make_repo(tmp_path)  # path contains 'agent'
        add_worktree(repo, ".claude/worktrees/agent-x")
        res = run_script(repo)  # dry-run
        target_lines = [ln.strip() for ln in res.stdout.splitlines()
                        if ln.startswith("  ")]
        assert str(repo.resolve()) not in target_lines  # never a target
        assert any("agent-x" in ln for ln in target_lines)

    def test_outside_prefix_skipped(self, tmp_path):
        repo = make_repo(tmp_path)
        outside = add_worktree(repo, "elsewhere/agent-y")
        res = run_script(repo, "--yes")
        assert res.returncode == 0
        assert outside.exists()  # skipped, not removed

    def test_dry_run_default_removes_nothing(self, tmp_path):
        repo = make_repo(tmp_path)
        wt = add_worktree(repo, ".claude/worktrees/agent-x")
        res = run_script(repo)
        assert res.returncode == 0
        assert wt.exists()
        assert "dry-run" in res.stdout.lower()

    def test_yes_removes_whitelisted_only(self, tmp_path):
        repo = make_repo(tmp_path)
        wt = add_worktree(repo, ".claude/worktrees/agent-x")
        keep = add_worktree(repo, "elsewhere/agent-y")
        res = run_script(repo, "--yes")
        assert res.returncode == 0, res.stderr
        assert not wt.exists()
        assert keep.exists()
        assert repo.exists() and (repo / ".git").exists()

    def test_remove_failure_is_loud_no_fallback(self, tmp_path):
        """A dirty worktree makes ``git worktree remove`` fail: the run
        must exit non-zero, keep the worktree on disk, and never fall
        back to raw deletion."""
        repo = make_repo(tmp_path)
        wt = add_worktree(repo, ".claude/worktrees/agent-x")
        (wt / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        res = run_script(repo, "--yes")
        assert res.returncode != 0
        assert wt.exists() and (wt / "dirty.txt").exists()
        assert "agent-x" in (res.stdout + res.stderr)


def test_script_contains_no_deletion_fallback():
    """Static guard: the script must never contain raw-deletion escape
    hatches (the incident's kill shot)."""
    src = SCRIPT.read_text(encoding="utf-8")
    for banned in ("rm -rf", "rmtree", "Remove-Item", "unlink(",
                   "2>/dev/null", "--force"):
        assert banned not in src, f"banned token in script: {banned}"
