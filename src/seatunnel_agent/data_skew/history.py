# -*- coding: utf-8 -*-
"""JSONL analysis history for the Data Skew agent (``logs/data_skew.jsonl``).

Same best-effort semantics as the impact/lineage loggers: logging never
breaks an analysis, the file rotates at 10 MB, and ``recent(n)`` feeds the
UI's history panel and future stats CLIs.  The full SQL (capped) is stored
so the UI can reload a past analysis into the editor.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .report import Severity, SkewReport

_MAX_BYTES = 10 * 1024 * 1024
_MAX_SQL_CHARS = 20_000


def default_history() -> "SkewHistory":
    """History at logs/data_skew.jsonl, or wherever
    ``SEATUNNEL_SKEW_HISTORY_PATH`` points (test isolation, like the
    settings-store override)."""
    import os
    override = os.environ.get("SEATUNNEL_SKEW_HISTORY_PATH")
    h = SkewHistory()
    if override:
        h.log_file = Path(override)
        h.log_dir = h.log_file.parent
    return h


class SkewHistory:
    """Append-only JSONL history of skew analyses."""

    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "data_skew.jsonl"
        self._lock = threading.Lock()

    def log(
        self,
        sql: str,
        report: SkewReport,
        mode: str,                # static | llm
        source: str = "ui",       # ui | cli | mcp
    ) -> None:
        counts = {
            "high": sum(1 for f in report.findings if f.severity == Severity.HIGH),
            "medium": sum(1 for f in report.findings if f.severity == Severity.MEDIUM),
            "low": sum(1 for f in report.findings if f.severity == Severity.LOW),
        }
        verdict = ("high" if counts["high"]
                   else "medium" if counts["medium"] else "clean")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": mode,
            "dialect": report.dialect,
            "counts": counts,
            "verdict": verdict,
            "optimized": bool(report.optimized_sql),
            "sql": (sql or "")[:_MAX_SQL_CHARS],
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # history is best-effort; never break the analysis

    def log_verify(
        self,
        sql: str,
        targets: int,
        confirmed: int,
        source: str = "ui",
    ) -> None:
        """A live-probe verification record (mode='verify'): which SQLs had
        their skew measured, and whether it was confirmed."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": "verify",
            "dialect": "",
            "counts": {"high": 0, "medium": 0, "low": 0},
            "verdict": "high" if confirmed else "clean",
            "probes": {"targets": targets, "confirmed": confirmed},
            "sql": (sql or "")[:_MAX_SQL_CHARS],
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # history is best-effort; never break the analysis

    def log_splitkey(
        self,
        table: str,
        partition_column: str,
        verdict: str,          # good | suspect | bad | low_ndv | null | none
        candidates: int = 0,
        source: str = "ui",
    ) -> None:
        """A SeaTunnel split-key check record (mode='splitkey'). The counts
        encode the configured key's verdict so the history table's marks
        stay meaningful: bad-ish → high, suspect/unconfigured → medium."""
        counts = {"high": 0, "medium": 0, "low": 0}
        if verdict in ("bad", "low_ndv", "null"):
            counts["high"] = 1
        elif verdict in ("suspect", "none"):
            counts["medium"] = 1
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": "splitkey",
            "dialect": "",
            "counts": counts,
            "verdict": ("high" if counts["high"]
                        else "medium" if counts["medium"] else "clean"),
            "splitkey": {"table": table, "partition_column": partition_column,
                         "key_verdict": verdict, "candidates": candidates},
            "sql": f"-- splitkey: {table} partition_column={partition_column or '(none)'}",
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # history is best-effort; never break the analysis

    def last_splitkey(self, table: str) -> dict | None:
        """The most recent splitkey record for *table*, or None.

        Feeds the re-check comparison line: run the check, change the
        config, run it again — the report says whether the fix landed."""
        if not table:
            return None
        for rec in self.recent(200):
            if rec.get("mode") != "splitkey":
                continue
            if (rec.get("splitkey") or {}).get("table") == table:
                return rec
        return None

    def recent(self, n: int = 20) -> list[dict]:
        """Latest *n* records, newest first.  [] on any problem."""
        try:
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
            if len(out) >= n:
                break
        return out

    def _rotate_if_needed(self) -> None:
        try:
            if (self.log_file.exists()
                    and self.log_file.stat().st_size > _MAX_BYTES):
                self.log_file.replace(
                    self.log_file.with_suffix(".jsonl.1"))
        except OSError:
            pass
