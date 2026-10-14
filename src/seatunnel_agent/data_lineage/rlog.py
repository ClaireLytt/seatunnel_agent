"""Structured (JSON lines) lineage query history for observability.

Every query is appended to logs/lineage.jsonl as one JSON object per line.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..jsonl_log import JsonlLog

_MAX_QUERY_CHARS = 300  # keep one JSONL line readable even for pasted SQL


class LineageLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "lineage.jsonl"
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

    def log(
        self,
        query: str,
        direction: str = "",
        mode: str = "static",
        source: str = "cli",
        graph_stats: dict[str, Any] | None = None,
        chain_stats: dict[str, int] | None = None,
        elapsed_ms: int | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": mode,
            "query": query[:_MAX_QUERY_CHARS],
            "direction": direction,
            "graph_stats": graph_stats or {},
            "chain_stats": chain_stats or {},
        }
        if elapsed_ms is not None:
            record["elapsed_ms"] = elapsed_ms
        self._log.append(record)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)
