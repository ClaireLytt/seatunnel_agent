"""JSONL run history for the hygiene agent (logs/hygiene.jsonl).

The mechanics live in :class:`seatunnel_agent.common.run_logger.RunLogger`;
this adapter only names the log and summarizes a report, so governance work
stays measurable ("12 orphans last month, 8 now") without a second logger
implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seatunnel_agent.common.run_logger import RunLogger

from .analyzer import HygieneReport


def _summarize(report: HygieneReport) -> dict[str, Any]:
    return {
        "root": report.root[:200],
        "tables_seen": report.tables_seen,
        "counts": report.counts(),
        "exempted": len(report.exempted),
        "orphans": [i.table for i in report.orphan_outputs][:10],
    }


class HygieneLogger(RunLogger):
    def __init__(self, log_dir: str | Path = "logs") -> None:
        super().__init__("hygiene", _summarize, log_dir)
