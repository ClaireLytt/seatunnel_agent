"""JSONL run history for the migration-guard agent (logs/ddlguard.jsonl).

The mechanics live in :class:`seatunnel_agent.common.run_logger.RunLogger`;
this adapter only names the log and summarizes a report, so dangerous-op
counts stay trendable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seatunnel_agent.common.run_logger import RunLogger

from .guard import GuardReport


def _summarize(report: GuardReport) -> dict[str, Any]:
    return {
        "root": report.root[:200],
        "statements_seen": report.statements_seen,
        "counts": report.counts(),
    }


class DdlGuardLogger(RunLogger):
    def __init__(self, log_dir: str | Path = "logs") -> None:
        super().__init__("ddlguard", _summarize, log_dir)
