"""JSONL run history for the grant-surface agent (logs/grants.jsonl).

The mechanics live in :class:`seatunnel_agent.common.run_logger.RunLogger`;
this adapter only names the log and summarizes a report, so the exposed
surface stays trendable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seatunnel_agent.common.run_logger import RunLogger

from .scanner import GrantReport


def _summarize(report: GrantReport) -> dict[str, Any]:
    return {
        "root": report.root[:200],
        "grants_seen": report.grants_seen,
        "revokes_seen": report.revokes_seen,
        "effective": len(report.effective),
        "sensitive_tables": len(report.sensitive_tables),
        "counts": report.counts(),
    }


class GrantsLogger(RunLogger):
    def __init__(self, log_dir: str | Path = "logs") -> None:
        super().__init__("grants", _summarize, log_dir)
