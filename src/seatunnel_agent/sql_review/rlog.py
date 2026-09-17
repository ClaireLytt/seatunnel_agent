"""Structured (JSON lines) review history for observability.

Every review is appended to logs/sql_review.jsonl as one JSON object per
line: timestamp, source, dialect, mode, target label, stats, finding
categories/severities and a SQL preview. `summarize` aggregates the history
into totals and the most frequent problem categories.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import CHECK_CATALOG, Finding

_MAX_LOG_BYTES = 10 * 1024 * 1024  # 10 MB
_SQL_PREVIEW_CHARS = 300


class ReviewLogger:
    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "sql_review.jsonl"
        self._lock = threading.Lock()

    def log(
        self,
        sql: str,
        dialect: str,
        mode: str,
        findings: list[Finding],
        stats: dict[str, int] | None = None,
        target: str | None = None,
        source: str = "cli",
        elapsed_ms: int | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": mode,
            "dialect": dialect,
            "target": target,
            "sql_preview": sql[:_SQL_PREVIEW_CHARS],
            "stats": stats or {},
            "categories": [f.category for f in findings],
            "severities": dict(Counter(f.severity.value for f in findings)),
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
            pass  # history is best-effort; never break the review itself

    @property
    def _rotated_path(self) -> Path:
        return self.log_file.with_name(self.log_file.stem + ".1.jsonl")

    def _rotate_if_needed(self) -> None:
        if self.log_file.is_file() and self.log_file.stat().st_size > _MAX_LOG_BYTES:
            rotated = self._rotated_path
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

    def summarize(self, n: int | None = None) -> dict[str, Any]:
        """Aggregate history: totals, severity counts, top problem categories."""
        records = self.recent(n if n is not None else 10**6)
        cat_counter: Counter[str] = Counter()
        sev_counter: Counter[str] = Counter()
        for r in records:
            cat_counter.update(r.get("categories", []))
            for sev, cnt in (r.get("severities") or {}).items():
                sev_counter[sev] += cnt
        return {
            "reviews": len(records),
            "findings": sum(cat_counter.values()),
            "severities": dict(sev_counter),
            "top_categories": [
                {
                    "category": cat,
                    "label": CHECK_CATALOG.get(cat, cat),
                    "count": cnt,
                }
                for cat, cnt in cat_counter.most_common(10)
            ],
        }
