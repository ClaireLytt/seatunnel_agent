"""Structured (JSON lines) lineage query history for observability.

Every query is appended to logs/lineage.jsonl as one JSON object per line.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_QUERY_CHARS = 300  # keep one JSONL line readable even for pasted SQL


class LineageLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "lineage.jsonl"
        self._lock = threading.Lock()

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
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # history is best-effort; never break the query itself

    def _rotate_if_needed(self) -> None:
        if self.log_file.is_file() and self.log_file.stat().st_size > _MAX_LOG_BYTES:
            rotated = self.log_file.with_name(self.log_file.stem + ".1.jsonl")
            if rotated.exists():
                rotated.unlink()
            self.log_file.rename(rotated)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            if not self.log_file.is_file():
                return []
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        for line in lines[-n:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
