"""Generic JSONL run-history logger for analysis agents.

HygieneLogger and MetaQualityLogger were rename-twins (a 27-line diff);
this module is the one implementation behind that seam. An agent supplies
its log name and a ``summarize`` function turning a report into the record
body; timestamping, the source tag, rotation (via JsonlLog) and ``recent``
live here once.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.jsonl_log import JsonlLog


class RunLogger:
    def __init__(self, name: str,
                 summarize: Callable[[Any], dict[str, Any]],
                 log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / f"{name}.jsonl"
        self._summarize = summarize
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

    def log_run(self, report: Any, source: str = "cli") -> None:
        self._log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "source": source,
            **self._summarize(report),
        })

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)
