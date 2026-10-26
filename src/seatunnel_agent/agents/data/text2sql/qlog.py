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


def insights(
    entries: list[dict[str, Any]],
    example_store: Any = None,
    top: int = 10,
) -> dict[str, Any]:
    """Flywheel-operations summary over qlog entries, LLM-free.

    Surfaces the questions worth curating: the top repeated interactive
    questions and whether each already has a verified example (= semantic
    cache coverage), the failure clusters, the slowest queries and the
    source mix. Non-interactive rows (bracketed channel tags such as
    "[subscription] ...") are excluded from the question ranking.
    """
    from .examples import normalize_question

    by_question: dict[str, dict[str, Any]] = {}
    sources: dict[str, int] = {}
    failures: dict[str, dict[str, Any]] = {}
    interactive_total = 0
    for e in entries:
        src = str(e.get("source", "") or "unknown")
        sources[src] = sources.get(src, 0) + 1
        q_raw = str(e.get("user_query", "")).strip()
        if not q_raw or q_raw.startswith("["):
            continue
        key = normalize_question(q_raw)
        if not key:
            continue
        interactive_total += 1
        slot = by_question.setdefault(
            key, {"question": q_raw, "count": 0, "ok": 0},
        )
        slot["count"] += 1
        if e.get("status") == "success":
            slot["ok"] += 1
        else:
            f = failures.setdefault(key, {"question": q_raw, "count": 0})
            f["count"] += 1
            if e.get("error"):
                f["last_error"] = str(e.get("error"))[:200]

    def _has_example(q: str) -> bool:
        if example_store is None:
            return False
        try:
            return example_store.exact_match(q) is not None
        except Exception:
            return False

    ranked = sorted(
        by_question.values(), key=lambda s: s["count"], reverse=True,
    )[:top]
    top_questions = [
        {
            "question": s["question"],
            "count": s["count"],
            "success": s["ok"],
            "has_example": _has_example(s["question"]),
        }
        for s in ranked
    ]
    covered = sum(
        s["count"] for s in by_question.values()
        if _has_example(s["question"])
    )
    slow = sorted(
        (e for e in entries if e.get("exec_time_ms")),
        key=lambda e: e.get("exec_time_ms") or 0, reverse=True,
    )[:top]
    return {
        "total": len(entries),
        "interactive_total": interactive_total,
        "cache_coverage_pct": (
            round(covered / interactive_total * 100, 1)
            if interactive_total else None
        ),
        "top_questions": top_questions,
        "failures": sorted(
            failures.values(), key=lambda f: f["count"], reverse=True,
        )[:top],
        "slow_queries": [
            {
                "user_query": e.get("user_query", ""),
                "exec_time_ms": e.get("exec_time_ms"),
                "source": e.get("source", ""),
            }
            for e in slow
        ],
        "sources": sources,
    }
