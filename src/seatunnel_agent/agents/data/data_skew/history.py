"""JSONL analysis history for the Data Skew agent (``logs/data_skew.jsonl``).

Same best-effort semantics as the impact/lineage loggers: logging never
breaks an analysis, the file rotates at 10 MB, and ``recent(n)`` feeds the
UI's history panel and future stats CLIs.  The full SQL (capped) is stored
so the UI can reload a past analysis into the editor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from seatunnel_agent.common.jsonl_log import JsonlLog

from .report import Severity, SkewReport

_MAX_SQL_CHARS = 20_000


def default_history() -> SkewHistory:
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
        self._log = JsonlLog(lambda: self.log_file, rotate="rename")

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
        self._log.append(record)

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
        self._log.append(record)

    def log_splitkey(
        self,
        table: str,
        partition_column: str,
        verdict: str,          # good | suspect | bad | low_ndv | null | none
        candidates: int = 0,
        source: str = "ui",
        top1_pct: float | None = None,
        ndv: int | None = None,
        null_pct: float | None = None,
    ) -> None:
        """A SeaTunnel split-key check record (mode='splitkey'). The counts
        encode the configured key's verdict so the history table's marks
        stay meaningful: bad-ish → high, suspect/unconfigured → medium.
        The measured metrics (top1/ndv/null of the configured key), when
        given, feed the trend view and the re-check drift line."""
        counts = {"high": 0, "medium": 0, "low": 0}
        if verdict in ("bad", "low_ndv", "null"):
            counts["high"] = 1
        elif verdict in ("suspect", "none"):
            counts["medium"] = 1
        sk: dict = {"table": table, "partition_column": partition_column,
                    "key_verdict": verdict, "candidates": candidates}
        if top1_pct is not None:
            sk["top1_pct"] = round(float(top1_pct), 2)
        if ndv is not None:
            sk["ndv"] = int(ndv)
        if null_pct is not None:
            sk["null_pct"] = round(float(null_pct), 2)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": "splitkey",
            "dialect": "",
            "counts": counts,
            "verdict": ("high" if counts["high"]
                        else "medium" if counts["medium"] else "clean"),
            "splitkey": sk,
            "sql": f"-- splitkey: {table} partition_column={partition_column or '(none)'}",
        }
        self._log.append(record)

    def log_runtime(
        self,
        app: str,
        stages: int,
        confirmed: int,
        suspect: int,
        source: str = "ui",
    ) -> None:
        """A runtime diagnosis record (mode='runtime'): Spark task-metric
        analysis of one application (event log or History Server)."""
        counts = {"high": confirmed, "medium": suspect, "low": 0}
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": "runtime",
            "dialect": "",
            "counts": counts,
            "verdict": ("high" if confirmed
                        else "medium" if suspect else "clean"),
            "runtime": {"app": app, "stages": stages,
                        "confirmed": confirmed, "suspect": suspect},
            "sql": f"-- runtime: {app}",
        }
        self._log.append(record)

    def log_drift(
        self,
        table: str,
        verdict: str,          # drift | stable | insufficient
        drifted_metrics: list[str] | None = None,
        source: str = "cli",
        deltas: dict[str, float] | None = None,
    ) -> None:
        """A drift patrol record (mode='drift'): the latest splitkey
        measurement compared against its historical baseline. ``deltas``
        (metric -> delta) feed the alert-suppression comparison."""
        counts = {"high": 1 if verdict == "drift" else 0, "medium": 0, "low": 0}
        drift: dict = {"table": table, "drift_verdict": verdict,
                       "metrics": drifted_metrics or []}
        if deltas:
            drift["deltas"] = {k: round(float(v), 2) for k, v in deltas.items()}
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "mode": "drift",
            "dialect": "",
            "counts": counts,
            "verdict": "high" if verdict == "drift" else "clean",
            "drift": drift,
            "sql": f"-- drift: {table} {verdict}",
        }
        self._log.append(record)

    def last_drift(self, table: str) -> dict | None:
        """The most recent drift patrol record for *table*, or None —
        the alert-suppression baseline (was this drift already reported?)."""
        if not table:
            return None
        for rec in self.recent(200):
            if (rec.get("mode") == "drift"
                    and (rec.get("drift") or {}).get("table") == table):
                return rec
        return None

    def last_runtime(self, app: str) -> dict | None:
        """The most recent runtime record for *app*, or None — feeds the
        runtime re-check line (did the fix land between two diagnoses?)."""
        if not app:
            return None
        for rec in self.recent(200):
            if (rec.get("mode") == "runtime"
                    and (rec.get("runtime") or {}).get("app") == app):
                return rec
        return None

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

    def splitkey_trend(self, table: str, n: int = 10) -> list[dict]:
        """The last *n* splitkey records for *table*, oldest first — the
        per-table patrol trend (verdict + measured top1)."""
        if not table:
            return []
        hits = [rec for rec in self.recent(500)
                if rec.get("mode") == "splitkey"
                and (rec.get("splitkey") or {}).get("table") == table]
        return list(reversed(hits[:n]))

    def splitkey_tables(self, n: int = 500) -> list[str]:
        """Tables with at least one splitkey record, most recent first."""
        seen: list[str] = []
        for rec in self.recent(n):
            if rec.get("mode") != "splitkey":
                continue
            t = str((rec.get("splitkey") or {}).get("table") or "")
            if t and t not in seen:
                seen.append(t)
        return seen

    def recent(self, n: int = 20) -> list[dict]:
        """Latest *n* records, newest first.  [] on any problem."""
        return list(reversed(self._log.recent(n)))
