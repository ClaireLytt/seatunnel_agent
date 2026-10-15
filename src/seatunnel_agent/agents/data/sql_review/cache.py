"""Persistent LLM review cache for the live review path.

The harness already replays LLM conclusions out of the review log; this
cache does the same for live reviews: reviewing the identical SQL again
with the same dialect, language, model, schema and rule configuration
returns the stored conclusion without spending tokens. Entries live in a
JSON-lines file next to the review log (``logs/sql_review_cache.jsonl``);
set ``SQLREVIEW_CACHE=0`` to disable.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG, ReviewConfig
from .report import Finding, ReviewReport, Severity, TableLineage
from .rlog import default_log_dir, sql_hash

_MAX_FILE_BYTES = 5 * 1024 * 1024
_SQL_PREVIEW_CHARS = 300


def cache_enabled() -> bool:
    return os.getenv("SQLREVIEW_CACHE", "1").strip().lower() not in (
        "0", "false", "off", "no",
    )


def config_fingerprint(config: ReviewConfig | None) -> str:
    """Stable digest of every rule-affecting ReviewConfig field."""
    cfg = config or DEFAULT_CONFIG
    doc = {
        "partition_cols": list(cfg.partition_cols),
        "incremental_suffixes": list(cfg.incremental_suffixes),
        "disabled_categories": sorted(cfg.disabled_categories),
        "severity_overrides": {
            k: v.value for k, v in sorted(cfg.severity_overrides.items())
        },
        "custom_rules": [
            [r.pattern, r.message, r.severity.value, r.category, r.suggestion]
            for r in cfg.custom_rules
        ],
        "thresholds": [
            cfg.max_subquery_depth, cfg.max_joins, cfg.max_stmt_lines,
            cfg.readability_min_lines, cfg.max_custom_matches,
            cfg.deep_offset_threshold, cfg.select_star_wide_cols,
        ],
    }
    raw = json.dumps(doc, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def store_fingerprint(store: Any) -> str:
    """Digest of the loaded schema (a schema change must invalidate hits)."""
    if store is None or len(store) == 0:
        return "-"
    parts = []
    for t in sorted(store.tables, key=lambda t: t.full_name.lower()):
        cols = ",".join(
            f"{c.name}:{c.dtype}" for c in t.columns + t.partition_columns
        )
        parts.append(f"{t.full_name.lower()}({cols})")
    raw = ";".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _finding_to_doc(f: Finding) -> dict[str, Any]:
    return {**f.to_dict(), "key": f.key, "args": f.args}


def _finding_from_doc(d: dict[str, Any]) -> Finding | None:
    try:
        severity = Severity(str(d.get("severity", "")).lower())
    except ValueError:
        return None
    return Finding(
        severity=severity,
        category=str(d.get("category", "")),
        description=str(d.get("description", "")),
        location=str(d.get("location", "")),
        impact=str(d.get("impact", "")),
        suggestion=str(d.get("suggestion", "")),
        source=str(d.get("source", "llm")),
        key=str(d.get("key", "")),
        args=d.get("args") or {},
    )


class ReviewCache:
    """Thread-safe append-only JSONL cache; last write per key wins."""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        base = Path(cache_dir) if cache_dir is not None else Path(default_log_dir())
        self.cache_file = base / "sql_review_cache.jsonl"
        self._lock = threading.Lock()

    @staticmethod
    def cache_key(
        sql: str, dialect: str, lang: str = "zh", model: str = "",
        config: ReviewConfig | None = None, store: Any = None,
    ) -> str:
        return ":".join((
            sql_hash(sql), dialect, lang, model or "-",
            config_fingerprint(config), store_fingerprint(store),
        ))

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.cache_file.is_file():
            return {}
        entries: dict[str, dict[str, Any]] = {}
        try:
            lines = self.cache_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = rec.get("key")
            if key:
                entries[key] = rec
        return entries

    def get(
        self, sql: str, dialect: str, lang: str = "zh", model: str = "",
        config: ReviewConfig | None = None, store: Any = None,
    ) -> tuple[str, ReviewReport] | None:
        """Return (rendered report, ReviewReport) on a hit, else None."""
        key = self.cache_key(sql, dialect, lang, model, config, store)
        with self._lock:
            rec = self._load().get(key)
        if rec is None or not rec.get("report_md"):
            return None
        findings = [
            f for f in (_finding_from_doc(d) for d in rec.get("findings", []))
            if f is not None
        ]
        lineage = None
        lin = rec.get("lineage")
        if isinstance(lin, dict):
            lineage = TableLineage(
                sources=list(lin.get("sources", [])),
                targets=list(lin.get("targets", [])),
                columns=list(lin.get("columns", [])),
            )
        report = ReviewReport(
            findings=findings,
            summary=str(rec.get("summary", "")),
            dialect=dialect,
            lineage=lineage,
        )
        return str(rec["report_md"]), report

    def put(
        self, sql: str, dialect: str, report: ReviewReport, report_md: str,
        lang: str = "zh", model: str = "",
        config: ReviewConfig | None = None, store: Any = None,
    ) -> None:
        rec = {
            "key": self.cache_key(sql, dialect, lang, model, config, store),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dialect": dialect,
            "lang": lang,
            "model": model,
            "sql_preview": sql[:_SQL_PREVIEW_CHARS],
            "sql_sha256": sql_hash(sql),
            "summary": report.summary,
            "report_md": report_md,
            "findings": [_finding_to_doc(f) for f in report.findings],
        }
        if report.lineage:
            rec["lineage"] = report.lineage.to_dict()
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._compact_if_needed()
                with open(self.cache_file, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # the cache is best-effort; never break the review itself

    def _compact_if_needed(self) -> None:
        """Rewrite keeping only the latest record per key when the file grows."""
        try:
            if (not self.cache_file.is_file()
                    or self.cache_file.stat().st_size <= _MAX_FILE_BYTES):
                return
            entries = self._load()
            tmp = self.cache_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                for rec in entries.values():
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            tmp.replace(self.cache_file)
        except OSError:
            pass
