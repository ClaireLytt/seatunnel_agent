"""JSONL run history for the metadata-quality agent (logs/metaquality.jsonl).

The mechanics live in :class:`seatunnel_agent.common.run_logger.RunLogger`;
this adapter only names the log and summarizes a report, so coverage and
anti-pattern counts stay trendable without a second logger implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seatunnel_agent.common.run_logger import RunLogger

from .checker import MetaQualityReport


def _summarize(report: MetaQualityReport) -> dict[str, Any]:
    covered = sum(c.commented for c in report.coverage)
    total = sum(c.total for c in report.coverage)
    return {
        "root": report.root[:200],
        "tables_checked": report.tables_checked,
        "counts": report.counts(),
        "comment_pct": round(100 * covered / total) if total else 100,
    }


class MetaQualityLogger(RunLogger):
    def __init__(self, log_dir: str | Path = "logs") -> None:
        super().__init__("metaquality", _summarize, log_dir)
