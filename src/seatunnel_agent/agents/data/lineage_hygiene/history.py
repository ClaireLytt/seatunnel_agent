"""JSONL run history for the hygiene agent (logs/hygiene.jsonl).

Same best-effort semantics as the lineage query log: never breaks the
analysis, rotates via JsonlLog, ``recent(n)`` feeds the stats CLI — so
governance work becomes measurable ("12 orphans last month, 8 now").
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.jsonl_log import JsonlLog

from .analyzer import HygieneReport


class HygieneLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "hygiene.jsonl"
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

    def log_run(self, report: HygieneReport, source: str = "cli") -> None:
        self._log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "source": source,
            "root": report.root[:200],
            "tables_seen": report.tables_seen,
            "counts": report.counts(),
            "exempted": len(report.exempted),
            "orphans": [i.table for i in report.orphan_outputs][:10],
        })

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)
