"""Data models for the UI testing agent.

TestCase/Step/Assertion describe a YAML case; StepLog/CaseResult/RunResult
capture one execution.  Everything is a plain dataclass so results serialize
with ``dataclasses.asdict`` for the JSON report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Verdict = Literal["PASS", "FAIL", "ERROR", "SKIP", "MANUAL"]


@dataclass
class Step:
    """One step: exactly one of *action* (deterministic) or *ai* (LLM loop)."""

    action: str | None = None          # click / fill / press / select / goto / ...
    args: dict[str, Any] = field(default_factory=dict)
    ai: str | None = None              # natural-language instruction for the agent
    note: str = ""                     # human description shown in the report

    @property
    def desc(self) -> str:
        if self.note:
            return self.note
        if self.ai:
            return f"ai: {self.ai}"
        return f"{self.action}: {self.args}"


@dataclass
class Assertion:
    kind: str                          # text_contains / value_is / options_are /
                                       # options_count / status_ok / status_error /
                                       # visible / hidden / ai_judge
    args: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    @property
    def desc(self) -> str:
        if self.note:
            return self.note
        return f"{self.kind}: {self.args}"


@dataclass
class TestCase:
    id: str                            # matches the manual checklist: A1 / B3 / C3 ...
    title: str
    tags: list[str] = field(default_factory=list)   # smoke/full/hive/sqlite/slow/manual
    page: str = "/datacompare"         # starting route
    lang: str = "zh"                   # UI language for the case (zh|en)
    setup: list[Step] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    expect: list[Assertion] = field(default_factory=list)
    timeout_s: int = 90                # hard cap per case


@dataclass
class StepLog:
    desc: str
    ok: bool
    elapsed_ms: int
    detail: str = ""                   # locator used / agent rounds / error summary
    screenshot: str | None = None      # path relative to runs/<ts>/


@dataclass
class CaseResult:
    case_id: str
    title: str
    verdict: Verdict
    steps: list[StepLog] = field(default_factory=list)
    asserts: list[StepLog] = field(default_factory=list)
    reason: str = ""                   # one-line FAIL/ERROR cause
    tokens: int = 0
    elapsed_ms: int = 0


@dataclass
class RunResult:
    started_at: str
    suite: str
    cases: list[CaseResult] = field(default_factory=list)
    app_log_tail: str = ""
    elapsed_ms: int = 0
    tokens: int = 0

    def counts(self) -> dict[str, int]:
        out = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0, "MANUAL": 0}
        for c in self.cases:
            out[c.verdict] += 1
        return out
