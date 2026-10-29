"""JSONL run history for the metadata-quality agent (logs/metaquality.jsonl).

Mirrors lineage_hygiene.history — ``recent(n)`` feeds the stats CLI so
comment-coverage and anti-pattern counts become trendable over time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.jsonl_log import JsonlLog

from .checker import MetaQualityReport


class MetaQualityLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "metaquality.jsonl"
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

    def log_run(self, report: MetaQualityReport, source: str = "cli") -> None:
        covered = sum(c.commented for c in report.coverage)
        total = sum(c.total for c in report.coverage)
        self._log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "source": source,
            "root": report.root[:200],
            "tables_checked": report.tables_checked,
            "counts": report.counts(),
            "comment_pct": round(100 * covered / total) if total else 100,
        })

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)
