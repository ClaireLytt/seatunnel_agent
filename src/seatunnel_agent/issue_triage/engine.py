# -*- coding: utf-8 -*-
"""Issue-triage agent — dedupe, locate, label, draft a reply.

Tools: BM25 search over the repo's historical issues (dedupe), bounded grep
over the codebase (locate the module), and the doc index.  The final answer
must be JSON ({labels, duplicates, priority, reply}); parsing is defensive
and an unparseable reply degrades to an empty triage with the raw text kept.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agent_core import Step, ToolLoopAgent
from ..config import Settings

_SYSTEM = """\
You are an issue-triage agent for a software repository.

Given a new issue (title + body):
1. search_similar to find duplicates / related past issues.
2. search_code to locate the module the issue points at (optional).
3. search_docs when the question may be answered by documentation.

Then answer with ONLY a JSON object (no prose, no code fence):
{"labels": ["bug"|"enhancement"|"question"|"documentation", ...],
 "duplicates": [issue numbers that look like the same problem],
 "priority": "high"|"medium"|"low",
 "reply": "a short, friendly draft response in the issue's language"}
"""

_LABELS = {"bug", "enhancement", "question", "documentation"}


def load_issues(path: str | Path) -> list[dict[str, Any]]:
    """History issues from JSONL: {number, title, body, labels?, state?}."""
    issues = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("title"):
            issues.append(rec)
    return issues


def build_tools(issues: list[dict[str, Any]],
                repo_dir: str | Path | None = "."):
    from ..agent_core import ToolSpec
    from ..doc_qa.core import BM25Index, Chunk, get_index

    issue_index = BM25Index([
        Chunk(source=f"#{i.get('number', '?')}",
              title=str(i.get("title", "")),
              text=f"{i.get('title', '')}\n{i.get('body', '')}"
                   f"\nlabels: {', '.join(i.get('labels') or [])}"
                   f"\nstate: {i.get('state', '')}")
        for i in issues])

    def search_similar(query: str, k: int = 5) -> str:
        hits = issue_index.search(query, k=min(int(k), 10))
        if not hits:
            return "(no similar issue found)"
        return "\n\n".join(
            f"{c.source} (score {s:.2f}): {c.title}\n{c.text[:400]}"
            for c, s in hits)

    def search_code(pattern: str) -> str:
        if repo_dir is None or not Path(repo_dir).is_dir():
            return "(no repository available)"
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "grep", "-n", "-I",
                 "--max-count", "3", pattern],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "(code search unavailable)"
        out = (proc.stdout or "").strip()
        if not out:
            return "(no match)"
        lines = out.splitlines()[:40]
        return "\n".join(lines)

    def search_docs(query: str) -> str:
        hits = get_index().search(query, k=3)
        if not hits:
            return "(no doc passage found)"
        return "\n\n".join(f"{c.source}: {c.title}\n{c.text[:400]}"
                           for c, _s in hits)

    s = {"type": "string"}
    return [
        ToolSpec("search_similar", "在历史 issue 里检索相似问题(查重)。",
                 {"type": "object",
                  "properties": {"query": s, "k": {"type": "integer"}},
                  "required": ["query"]}, search_similar),
        ToolSpec("search_code", "git grep 代码定位相关模块(固定字符串)。",
                 {"type": "object", "properties": {"pattern": s},
                  "required": ["pattern"]}, search_code),
        ToolSpec("search_docs", "检索项目/连接器文档。",
                 {"type": "object", "properties": {"query": s},
                  "required": ["query"]}, search_docs),
    ]


@dataclass
class TriageResult:
    labels: list[str] = field(default_factory=list)
    duplicates: list[int] = field(default_factory=list)
    priority: str = "medium"
    draft: str = ""
    raw_reply: str = ""
    steps: list[Step] = field(default_factory=list)
    parsed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"labels": self.labels, "duplicates": self.duplicates,
                "priority": self.priority, "draft": self.draft,
                "parsed": self.parsed, "raw_reply": self.raw_reply,
                "steps": [s.to_dict() for s in self.steps]}


def _parse_reply(reply: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", reply or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def triage(title: str, body: str, settings: Settings,
           issues: list[dict[str, Any]] | None = None,
           repo_dir: str | Path | None = ".",
           max_steps: int = 6, client: Any = None,
           on_step=None) -> TriageResult:
    agent = ToolLoopAgent(settings,
                          tools=build_tools(issues or [], repo_dir),
                          system_prompt=_SYSTEM, agent_name="issue_triage",
                          max_steps=max_steps, client=client)
    loop = agent.run(f"TITLE: {title}\n\nBODY:\n{body}", on_step=on_step)
    result = TriageResult(raw_reply=loop.reply, steps=loop.steps)
    data = _parse_reply(loop.reply)
    if data is None:
        return result
    result.parsed = True
    result.labels = [str(x) for x in data.get("labels") or []
                     if str(x) in _LABELS]
    result.duplicates = [int(str(x).lstrip("#"))
                         for x in data.get("duplicates") or []
                         if str(x).lstrip("#").isdigit()][:10]
    prio = str(data.get("priority", "medium")).lower()
    result.priority = prio if prio in ("high", "medium", "low") else "medium"
    result.draft = str(data.get("reply", ""))
    return result
