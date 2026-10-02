# -*- coding: utf-8 -*-
"""Eval run history and regression compare.

Every run is appended to ``logs/llm_eval_runs.jsonl`` (``LLM_EVAL_LOG=0``
disables, ``LLM_EVAL_PATH`` relocates).  A *regression* against the previous
run of the same suite means: a case flipped pass→fail, or the suite score
dropped by more than :data:`SCORE_DROP_TOLERANCE`.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .runner import SuiteResult

SCORE_DROP_TOLERANCE = 0.01
_MAX_LOG_BYTES = 10 * 1024 * 1024


def log_path() -> Path:
    return Path(os.getenv("LLM_EVAL_PATH") or "logs/llm_eval_runs.jsonl")


class RunLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else log_path()
        self._lock = threading.Lock()

    def log(self, result: "SuiteResult") -> None:
        """Best-effort append; never raises into the run."""
        if os.getenv("LLM_EVAL_LOG", "1") == "0":
            return
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
            line = json.dumps(rec, ensure_ascii=False)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if (self.path.is_file()
                        and self.path.stat().st_size > _MAX_LOG_BYTES):
                    lines = self.path.read_text(
                        encoding="utf-8").splitlines()
                    self.path.write_text(
                        "\n".join(lines[len(lines) // 2:]) + "\n",
                        encoding="utf-8")
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:  # noqa: BLE001 — history is best-effort
            pass

    def recent(self, n: int = 50,
               suite: str | None = None) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if suite and rec.get("suite") != suite:
                continue
            out.append(rec)
        return out[-n:]

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
