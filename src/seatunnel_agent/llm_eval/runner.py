# -*- coding: utf-8 -*-
"""Eval runner: execute a suite against the LLM targets and score it.

Deterministic checks decide pass/fail; the optional LLM judge
(``judge=True``) adds advisory checks that are **excluded from the CI
gate** — a model grading a model must never block a release on its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import Settings
from .scoring import run_check
from .suite import Suite
from .targets import TARGETS

_JUDGE_SYSTEM = (
    "You are a strict grader. Given a RUBRIC and an OUTPUT, answer with "
    "exactly PASS or FAIL on the first line, then one short reason line.")


@dataclass
class CheckResult:
    type: str
    value: str
    passed: bool
    detail: str = ""
    advisory: bool = False  # judge checks never gate

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value, "passed": self.passed,
                "detail": self.detail, "advisory": self.advisory}


@dataclass
class CaseResult:
    id: str
    agent: str
    weight: float = 1.0
    checks: list[CheckResult] = field(default_factory=list)
    output: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    error: str | None = None

    @property
    def gating_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.advisory]

    @property
    def score(self) -> float:
        """Fraction of gating checks passed; an errored case scores 0."""
        if self.error:
            return 0.0
        gating = self.gating_checks
        if not gating:
            return 0.0
        return sum(1 for c in gating if c.passed) / len(gating)

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.gating_checks)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "agent": self.agent, "weight": self.weight,
                "score": round(self.score, 4), "passed": self.passed,
                "checks": [c.to_dict() for c in self.checks],
                "output": self.output, "usage": self.usage,
                "latency_ms": self.latency_ms, "error": self.error}


@dataclass
class SuiteResult:
    suite: str
    cases: list[CaseResult] = field(default_factory=list)
    elapsed_ms: int = 0

    @property
    def score(self) -> float:
        """Weighted mean of case scores."""
        total_w = sum(c.weight for c in self.cases)
        if not total_w:
            return 0.0
        return sum(c.score * c.weight for c in self.cases) / total_w

    @property
    def failed_cases(self) -> list[str]:
        return [c.id for c in self.cases if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {"suite": self.suite, "score": round(self.score, 4),
                "failed_cases": self.failed_cases,
                "cases": [c.to_dict() for c in self.cases],
                "elapsed_ms": self.elapsed_ms}


def run_suite(suite: Suite,
              settings: Settings | None = None,
              client_factory: Callable[[Settings], Any] | None = None,
              judge: bool = False,
              targets: dict[str, Callable] | None = None,
              ) -> SuiteResult:
    """Run every case; per-case errors are captured, never raised."""
    if client_factory is None:
        from .. import llm  # resolved at call time so tests can monkeypatch
        client_factory = lambda s: llm.LLMClient(s, agent="llm_eval")  # noqa: E731
    if settings is None:
        from ..config import load_settings
        settings = load_settings()
    targets = targets if targets is not None else TARGETS

    start = time.time()
    result = SuiteResult(suite=suite.name)
    for case in suite.cases:
        cr = CaseResult(id=case.id, agent=case.agent, weight=case.weight)
        try:
            adapter = targets[case.agent]
            out = adapter(case.input, settings, client_factory)
            cr.output = out.get("output", "")
            cr.usage = out.get("usage", {}) or {}
            cr.latency_ms = int(out.get("latency_ms", 0) or 0)
            for check in case.expect:
                if check.type == "judge":
                    if not judge:
                        continue  # advisory checks only run on request
                    cr.checks.append(_run_judge(check, cr.output, settings,
                                                client_factory))
                    continue
                passed, detail = run_check(check, cr.output)
                cr.checks.append(CheckResult(
                    type=check.type, value=check.value,
                    passed=passed, detail=detail))
        except Exception as exc:  # noqa: BLE001 — isolate the case
            cr.error = f"{type(exc).__name__}: {exc}"
        result.cases.append(cr)
    result.elapsed_ms = int((time.time() - start) * 1000)

    from .baseline import RunLogger
    RunLogger().log(result)
    return result


def _run_judge(check, output: str, settings: Settings,
               client_factory: Callable) -> CheckResult:
    try:
        client = client_factory(settings)
        resp = client.chat(_JUDGE_SYSTEM, [{
            "role": "user",
            "content": f"RUBRIC:\n{check.value}\n\nOUTPUT:\n{output}"}])
        text = (resp.reply_text or "").strip()
        passed = text.upper().startswith("PASS")
        return CheckResult(type="judge", value=check.value, passed=passed,
                           detail=text.splitlines()[0] if text else "(empty)",
                           advisory=True)
    except Exception as exc:  # noqa: BLE001 — judge is advisory
        return CheckResult(type="judge", value=check.value, passed=False,
                           detail=f"judge error: {exc}", advisory=True)
