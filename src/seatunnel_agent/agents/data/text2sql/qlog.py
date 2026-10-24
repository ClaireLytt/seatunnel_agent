"""Structured (JSON lines) query logging for observability.

Every executed query is appended as one JSON object per line with the
fields required by the PRD: timestamp, user question, matched tables,
generated SQL, execution time, row count, status.

Backed by ``common.jsonl_log.JsonlLog`` for append/rotate/tail-read.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seatunnel_agent.common.jsonl_log import JsonlLog


class QueryLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self._log = JsonlLog(
            self.log_dir / "text2sql_queries.jsonl",
            rotate="rename",
        )

    @property
    def log_file(self) -> Path:
        return self._log.path

    def log(
        self,
        user_query: str,
        generated_sql: str,
        status: str,
        matched_tables: list[str] | None = None,
        exec_time_ms: int | None = None,
        row_count: int | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not user_query.strip():
            # Never log an empty question — fall back to the channel tag so
            # every history row stays attributable ([mcp], [subscription], …).
            source = (extra or {}).get("source") or "unknown"
            user_query = f"[{source}]"
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_query": user_query,
            "matched_tables": matched_tables or [],
            "generated_sql": generated_sql,
            "exec_time_ms": exec_time_ms,
            "row_count": row_count,
            "status": status,
        }
        if error:
            record["error"] = error
        if extra:
            record.update(extra)
        self._log.append(record)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)

    def clear(self) -> None:
        """Remove all log entries (including rotated file)."""
        path = self._log.path
        rotated = path.with_name(path.stem + ".1.jsonl")
        with self._log._lock:
            if path.is_file():
                path.write_text("", encoding="utf-8")
            if rotated.is_file():
                rotated.unlink()

    def delete(self, indices_from_newest: list[int]) -> int:
        """Delete records by display index (0 = newest line in file).

        Returns the number of records actually deleted.
        """
        if not indices_from_newest:
            return 0
        path = self._log.path
        with self._log._lock:
            if not path.is_file():
                return 0
            lines = path.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            abs_indices = {total - 1 - i for i in indices_from_newest if 0 <= i < total}
            if not abs_indices:
                return 0
            remaining = [l for i, l in enumerate(lines) if i not in abs_indices]
            content = "\n".join(remaining) + ("\n" if remaining else "")
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, str(path))
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            return len(abs_indices)
