"""Structured (JSON lines) review history for observability.

Every review is appended to logs/sql_review.jsonl as one JSON object per
line: timestamp, source, dialect, mode, target label, stats, finding
categories/severities and a SQL preview. `summarize` aggregates the history
into totals and the most frequent problem categories.
"""

from __future__ import annotations

import hashlib
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.jsonl_log import JsonlLog
from .report import CHECK_CATALOG, Finding

_SQL_PREVIEW_CHARS = 300


def sql_hash(sql: str) -> str:
    """Stable key for matching the same SQL across logs (harness LLM cache)."""
    return hashlib.sha256((sql or "").strip().encode("utf-8")).hexdigest()


def default_log_dir() -> str:
    """Review-log directory: $SQLREVIEW_LOG_DIR, falling back to ./logs."""
    return os.getenv("SQLREVIEW_LOG_DIR") or "logs"


class ReviewLogger:
    def __init__(self, log_dir: str | Path | None = None) -> None:
        self.log_dir = Path(log_dir) if log_dir is not None else Path(default_log_dir())
        self.log_file = self.log_dir / "sql_review.jsonl"
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

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
            "sql_sha256": sql_hash(sql),
            "stats": stats or {},
            "categories": [f.category for f in findings],
            "severities": dict(Counter(f.severity.value for f in findings)),
        }
        if elapsed_ms is not None:
            record["elapsed_ms"] = elapsed_ms
        self._log.append(record)

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        return self._log.recent(n)

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
