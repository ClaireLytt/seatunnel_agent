# -*- coding: utf-8 -*-
"""Eval run history and regression compare.

Every run is appended to ``logs/llm_eval_runs.jsonl`` (``LLM_EVAL_LOG=0``
disables, ``LLM_EVAL_PATH`` relocates).  A *regression* against the previous
run of the same suite means: a case flipped pass→fail, or the suite score
dropped by more than :data:`SCORE_DROP_TOLERANCE`.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seatunnel_agent.common.jsonl_log import JsonlLog

if TYPE_CHECKING:  # pragma: no cover
    from .runner import SuiteResult

SCORE_DROP_TOLERANCE = 0.01


def log_path() -> Path:
    return Path(os.getenv("LLM_EVAL_PATH") or "logs/llm_eval_runs.jsonl")


class RunLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._log = JsonlLog(lambda: self.path, env_switch="LLM_EVAL_LOG")

    def log(self, result: "SuiteResult") -> None:
        """Best-effort append; never raises into the run."""
        try:
            rec = {
                "ts": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "suite": result.suite,
                "score": round(result.score, 4),
                "cases": {c.id: {"score": round(c.score, 4),
                                 "passed": c.passed}
                          for c in result.cases},
            }
        except Exception:  # noqa: BLE001 — history is best-effort
            return
        self._log.append(rec)

    def recent(self, n: int = 50,
               suite: str | None = None) -> list[dict[str, Any]]:
        where = (lambda rec: rec.get("suite") == suite) if suite else None
        return self._log.recent(n, where=where)

    def last_run(self, suite: str) -> dict[str, Any] | None:
        """The most recent logged run of *suite*.

        Callers fetch the baseline BEFORE run_suite() (which appends its own
        run at the end) — never by counting back from the tail afterwards:
        with LLM_EVAL_LOG=0 the current run is not in the log at all, and a
        failed best-effort append would silently shift the offset."""
        runs = self.recent(n=1000, suite=suite)
        return runs[-1] if runs else None


def compare(current: "SuiteResult",
            previous: dict[str, Any] | None) -> dict[str, Any]:
    """Regression verdict vs a logged previous run (None → no baseline)."""
    if previous is None:
        return {"has_baseline": False, "regressed": False,
                "regressed_cases": [], "score_drop": 0.0}
    prev_cases = previous.get("cases", {})
    regressed_cases = [
        c.id for c in current.cases
        if not c.passed and prev_cases.get(c.id, {}).get("passed")]
    score_drop = round(float(previous.get("score", 0.0)) - current.score, 4)
    return {
        "has_baseline": True,
        "regressed": bool(regressed_cases) or score_drop > SCORE_DROP_TOLERANCE,
        "regressed_cases": regressed_cases,
        "score_drop": score_drop,
    }
