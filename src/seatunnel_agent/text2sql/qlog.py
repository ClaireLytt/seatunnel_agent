"""Structured (JSON lines) query logging for observability.

Every executed query is appended as one JSON object per line with the
fields required by the PRD: timestamp, user question, matched tables,
generated SQL, execution time, row count, status.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QueryLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "text2sql_queries.jsonl"
        self._lock = threading.Lock()

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
        self.log_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            self._rotate_if_needed()
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)

    _MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB

    @property
    def _rotated_path(self) -> Path:
        return self.log_file.with_name(self.log_file.stem + ".1.jsonl")

    def _rotate_if_needed(self) -> None:
        if self.log_file.is_file() and self.log_file.stat().st_size > self._MAX_LOG_BYTES:
            rotated = self._rotated_path
            if rotated.exists():
                rotated.unlink()
            self.log_file.rename(rotated)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            if not self.log_file.is_file():
                return []
            size = self.log_file.stat().st_size
            if size == 0:
                return []
            chunk_size = min(size, n * 2048)
            with open(self.log_file, "rb") as f:
                f.seek(max(0, size - chunk_size))
                data = f.read().decode("utf-8", errors="replace")
        lines = data.splitlines()
        if chunk_size < size:
            lines = lines[1:]
        tail = lines[-n:] if len(lines) > n else lines
        records: list[dict[str, Any]] = []
        for line in tail:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def clear(self) -> None:
        """Remove all log entries (including rotated file)."""
        with self._lock:
            if self.log_file.is_file():
                self.log_file.write_text("", encoding="utf-8")
            if self._rotated_path.is_file():
                self._rotated_path.unlink()

    def delete(self, indices_from_newest: list[int]) -> int:
        """Delete records by display index (0 = newest line in file).

        Returns the number of records actually deleted.
        """
        if not indices_from_newest:
            return 0
        with self._lock:
            if not self.log_file.is_file():
                return 0
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            abs_indices = {total - 1 - i for i in indices_from_newest if 0 <= i < total}
            if not abs_indices:
                return 0
            remaining = [l for i, l in enumerate(lines) if i not in abs_indices]
            content = "\n".join(remaining) + ("\n" if remaining else "")
            self.log_file.write_text(content, encoding="utf-8")
            return len(abs_indices)
