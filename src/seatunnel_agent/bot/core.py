# -*- coding: utf-8 -*-
"""GitHub bot core — review a PR patch with the platform's own tools.

Deterministic and offline: input is a unified diff, output is one markdown
comment.  Checks run **on the added lines only** (a bot that nags about
pre-existing code gets muted within a week):

* secret scan over every added line (masked previews),
* static SQL review over the added content of ``*.sql`` files.

Network (fetching the diff, posting the comment) lives in server.py and is
injectable there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BOT_MARKER = "<!-- seatunnel-agent-bot -->"

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class PatchFile:
    path: str
    added: list[tuple[int, str]] = field(default_factory=list)  # (new line no, text)

    @property
    def added_text(self) -> str:
        return "\n".join(text for _no, text in self.added)


def parse_patch(patch: str) -> list[PatchFile]:
    """Unified diff → added lines per file (new-file line numbers)."""
    files: list[PatchFile] = []
    current: PatchFile | None = None
    new_no = 0
    for line in (patch or "").splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current = None if path == "/dev/null" else PatchFile(path=path)
            if current:
                files.append(current)
            continue
        if current is None:
            continue
        m = _HUNK_RE.match(line)
        if m:
            new_no = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current.added.append((new_no, line[1:]))
            new_no += 1
        elif line.startswith("\\"):
            continue  # "\ No newline at end of file" is not a content line
        elif not line.startswith("-"):
            new_no += 1
    return [f for f in files if f.added]


@dataclass
class BotFinding:
    tool: str          # secret_scan | sql_review
    severity: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "severity": self.severity,
                "path": self.path, "line": self.line,
                "message": self.message}


def _scan_secrets(files: list[PatchFile]) -> list[BotFinding]:
    from ..secret_scan import scan_text
    out: list[BotFinding] = []
    for f in files:
        hits = scan_text(f.added_text, name=f.path)
        for h in hits:
            # finding.line indexes the added-lines text → real new line no
            real = f.added[h.line - 1][0] if 0 < h.line <= len(f.added) else 0
            out.append(BotFinding(
                tool="secret_scan", severity=h.severity, path=f.path,
                line=real, message=f"{h.rule_name_zh} `{h.masked}`"))
    return out


def _review_sql(files: list[PatchFile]) -> list[BotFinding]:
    from ..sql_review.agent import static_review_report
    from ..sql_review.linter import normalize_dialect
    out: list[BotFinding] = []
    for f in files:
        if not f.path.lower().endswith(".sql"):
            continue
        try:
            rep = static_review_report(f.added_text,
                                       normalize_dialect("hive"))
        except Exception:  # noqa: BLE001 — a diff fragment may not parse
            continue
        for finding in rep.findings:
            sev = {"critical": "high", "risk": "medium"}.get(
                finding.severity.value, "low")
            out.append(BotFinding(
                tool="sql_review", severity=sev, path=f.path,
                line=f.added[0][0] if f.added else 0,
                message=finding.description))
    return out


_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
_SEV_MARK = {"high": "🔴", "medium": "🟠", "low": "🟡"}


def review_patch(patch: str) -> tuple[list[BotFinding], str]:
    """(findings, markdown comment).  Empty findings → empty comment."""
    files = parse_patch(patch)
    findings = _scan_secrets(files) + _review_sql(files)
    findings.sort(key=lambda f: (_SEV_ORDER.get(f.severity, 3),
                                 f.path, f.line))
    if not findings:
        return [], ""
    lines = [BOT_MARKER, "## 🤖 SeaTunnel Agent Bot", "",
             f"本次改动发现 **{len(findings)}** 处问题"
             f"(只检查新增行):", "",
             "| 级别 | 工具 | 位置 | 说明 |", "|---|---|---|---|"]
    for f in findings[:50]:
        mark = _SEV_MARK.get(f.severity, "🟡")
        lines.append(f"| {mark} {f.severity} | {f.tool} "
                     f"| `{f.path}:{f.line}` | {f.message} |")
    lines += ["",
              "> secret 预览已脱敏 · 本地复查:`seatunnel-agent secretscan"
              " <paths>` / `seatunnel-agent review <file.sql>`"]
    return findings, "\n".join(lines)
