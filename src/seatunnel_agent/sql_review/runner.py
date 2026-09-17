"""Batch-review helpers: collect SQL targets from a directory or git diff,
and the CI severity gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .report import Finding, Severity

_SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.RISK: 1, Severity.SUGGESTION: 2}


def collect_sql_files(directory: str | Path) -> list[Path]:
    """All *.sql files under *directory*, recursively, sorted."""
    return sorted(p for p in Path(directory).rglob("*.sql") if p.is_file())


def changed_sql_files(base: str = "HEAD", cwd: str | Path | None = None) -> list[Path]:
    """SQL files changed vs *base* (staged + unstaged) plus untracked ones."""
    start = Path(cwd) if cwd else Path(".")

    def _git(root: Path, *args: str) -> list[str]:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, encoding="utf-8", cwd=root,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 失败: {proc.stderr.strip()}")
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    # git diff prints paths relative to the repo root, not the cwd — resolve
    # the toplevel so running from a subdirectory still finds the files
    top = _git(start, "rev-parse", "--show-toplevel")
    root = Path(top[0]) if top else start

    names = _git(root, "diff", "--name-only", "--diff-filter=d", base, "--", "*.sql")
    names += _git(root, "ls-files", "--others", "--exclude-standard", "--", "*.sql")

    seen: set[str] = set()
    files: list[Path] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        p = root / name
        if p.is_file():
            files.append(p)
    return files


def severity_reached(findings: list[Finding], threshold: str) -> bool:
    """True when any finding is at or above *threshold* severity."""
    thr = _SEVERITY_RANK[Severity(threshold)]
    return any(_SEVERITY_RANK[f.severity] <= thr for f in findings)
