"""The ONLY sanctioned worktree-cleanup entry point (CLAUDE.md §9).

Codifies the 2026-10-22 incident rules in executable form:

- whitelist by RESOLVED FULL PREFIX ``<repo>/.claude/worktrees/agent-``,
  never by substring matching (the incident: ``grep agent`` matched the
  main repo's own path);
- one ``git worktree remove <path>`` per entry, tried WITHOUT force;
- any failure is loud: collected, printed, and fails the whole run with
  a non-zero exit — there is NO raw-deletion fallback of any kind;
- dry-run by default: prints the full target list; ``--yes`` executes;
- ``git worktree prune`` runs only after every removal succeeded.

Usage:  python scripts/cleanup_worktrees.py [--yes]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def repo_root() -> Path:
    res = _git("rev-parse", "--show-toplevel")
    if res.returncode != 0:
        print("not inside a git repository", file=sys.stderr)
        raise SystemExit(2)
    return Path(res.stdout.strip()).resolve()


def list_worktrees() -> list[Path]:
    res = _git("worktree", "list", "--porcelain")
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(2)
    return [Path(line[len("worktree "):]).resolve()
            for line in res.stdout.splitlines()
            if line.startswith("worktree ")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true",
                        help="actually remove (default: dry-run)")
    args = parser.parse_args()

    root = repo_root()
    prefix = root / ".claude" / "worktrees"
    targets: list[Path] = []
    skipped: list[Path] = []
    for wt in list_worktrees():
        if wt == root:
            continue  # the main checkout is never a target
        # resolved full-prefix check — NEVER substring matching
        if wt.parent == prefix and wt.name.startswith("agent-"):
            targets.append(wt)
        else:
            skipped.append(wt)

    for wt in skipped:
        print(f"skip (outside {prefix}\\agent-*): {wt}")
    if not targets:
        print("nothing to clean")
        return 0

    print("targets:")
    for wt in targets:
        print(f"  {wt}")
    if not args.yes:
        print("dry-run: nothing removed (pass --yes to execute)")
        return 0

    failures: list[tuple[Path, str]] = []
    for wt in targets:
        res = _git("worktree", "remove", str(wt))
        if res.returncode != 0:
            # loud, collected, NO fallback of any kind
            failures.append((wt, (res.stderr or res.stdout).strip()))
        else:
            print(f"removed: {wt}")

    if failures:
        print("FAILED (left in place, fix manually with git):",
              file=sys.stderr)
        for wt, err in failures:
            print(f"  {wt}\n    {err}", file=sys.stderr)
        return 1

    _git("worktree", "prune")
    print("prune done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
