"""JSONL run history for the data-contract agent (logs/contract.jsonl).

The mechanics live in :class:`seatunnel_agent.common.run_logger.RunLogger`;
this adapter only names the log and summarizes a report, so violation
counts stay trendable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from seatunnel_agent.common.run_logger import RunLogger

from .checker import ContractReport


def _summarize(report: ContractReport) -> dict[str, Any]:
    return {
        "root": report.root[:200],
        "tables_declared": report.tables_declared,
        "tables_checked": report.tables_checked,
        "counts": report.counts(),
    }


class ContractLogger(RunLogger):
    def __init__(self, log_dir: str | Path = "logs") -> None:
        super().__init__("contract", _summarize, log_dir)
