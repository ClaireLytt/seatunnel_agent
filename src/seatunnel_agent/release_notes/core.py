# -*- coding: utf-8 -*-
"""Release-notes core — classify commits, group a changelog, suggest a bump.

Deterministic: input is plain ``sha<TAB>subject`` lines (what
``git log --format=%h%x09%s`` prints), classification follows conventional
commits (``type(scope)!: subject``), and the version suggestion is plain
semver (breaking → major, feat → minor, else patch).  Git itself is only
touched by the CLI/UI convenience helpers, never by the core.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

_CONVENTIONAL = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*"
    r"(?P<subject>.+)$")

# display order of changelog groups
GROUPS: list[tuple[str, str, str]] = [
    ("feat", "Features", "新功能"),
    ("fix", "Bug Fixes", "问题修复"),
    ("perf", "Performance", "性能优化"),
    ("refactor", "Refactoring", "重构"),
    ("docs", "Documentation", "文档"),
    ("test", "Tests", "测试"),
    ("chore", "Chores", "杂项"),
    ("other", "Other", "其他"),
]
_KNOWN_TYPES = {g[0] for g in GROUPS} - {"other"}
_TYPE_ALIASES = {"ci": "chore", "build": "chore", "style": "refactor"}


@dataclass
class Commit:
    sha: str
    subject: str          # subject without the type prefix
    raw: str
    ctype: str = "other"
    scope: str = ""
    breaking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"sha": self.sha, "subject": self.subject, "type": self.ctype,
                "scope": self.scope, "breaking": self.breaking}


@dataclass
class ReleaseNotes:
    commits: list[Commit] = field(default_factory=list)
    current_version: str = ""
    bump: str = "patch"            # major | minor | patch
    next_version: str = ""

    @property
    def breaking(self) -> list[Commit]:
        return [c for c in self.commits if c.breaking]

    def grouped(self) -> list[tuple[str, str, list[Commit]]]:
        """(group key, en label — zh resolved by the report) in GROUPS order."""
        by_type: dict[str, list[Commit]] = {}
        for c in self.commits:
            by_type.setdefault(c.ctype, []).append(c)
        return [(key, en, by_type[key]) for key, en, _zh in GROUPS
                if key in by_type]

    def to_dict(self) -> dict[str, Any]:
        return {"current_version": self.current_version, "bump": self.bump,
                "next_version": self.next_version,
                "breaking": [c.to_dict() for c in self.breaking],
                "commits": [c.to_dict() for c in self.commits]}


def parse_commit_lines(text: str) -> list[Commit]:
    """``sha<TAB>subject`` per line; lines without a TAB are treated as a
    bare subject (sha left empty) so pasted plain lists still work."""
    commits: list[Commit] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, subject = line.partition("\t")
        if not subject:
            sha, subject = "", sha
        commit = Commit(sha=sha.strip()[:12], subject=subject.strip(),
                        raw=subject.strip())
        m = _CONVENTIONAL.match(subject.strip())
        if m:
            ctype = m.group("type").lower()
            ctype = _TYPE_ALIASES.get(ctype, ctype)
            commit.ctype = ctype if ctype in _KNOWN_TYPES else "other"
            commit.scope = (m.group("scope") or "").strip()
            commit.subject = m.group("subject").strip()
            commit.breaking = bool(m.group("bang"))
        if "BREAKING CHANGE" in subject.upper().replace("-", " "):
            commit.breaking = True
        commits.append(commit)
    return commits


def suggest_bump(commits: list[Commit]) -> str:
    if any(c.breaking for c in commits):
        return "major"
    if any(c.ctype == "feat" for c in commits):
        return "minor"
    return "patch"


def next_semver(current: str, bump: str) -> str:
    """0.2.0 + minor → 0.3.0; tolerant of a leading 'v' and short versions."""
    raw = (current or "").strip().lstrip("vV")
    parts = raw.split(".") if raw else []
    try:
        nums = [int(re.match(r"\d+", p).group()) for p in parts[:3]]
    except (AttributeError, ValueError):
        nums = []
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def build_notes(log_text: str, current_version: str = "") -> ReleaseNotes:
    commits = parse_commit_lines(log_text)
    bump = suggest_bump(commits)
    return ReleaseNotes(
        commits=commits,
        current_version=(current_version or "").strip(),
        bump=bump,
        next_version=next_semver(current_version, bump),
    )


# ── CLI/UI convenience: read the log from an actual repo ───────────────────

def collect_git_log(repo: str = ".", since: str | None = None,
                    until: str = "HEAD") -> str:
    """``sha<TAB>subject`` lines from git; *since* defaults to the latest
    tag (falls back to the full history when the repo has no tags)."""
    def _git(*args: str) -> str:
        out = subprocess.run(["git", "-C", repo, *args],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip() or "git failed")
        return out.stdout

    if since is None:
        try:
            since = _git("describe", "--tags", "--abbrev=0").strip() or None
        except RuntimeError:
            since = None
    rev = f"{since}..{until}" if since else until
    return _git("log", "--format=%h%x09%s", rev)


def current_version_from_pyproject(repo: str = ".") -> str:
    """Best-effort ``version = "..."`` from pyproject.toml; '' if absent."""
    from pathlib import Path
    p = Path(repo) / "pyproject.toml"
    try:
        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"',
                      p.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""
