"""Shared helpers and tunables for the Data Comparison UI."""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from seatunnel_agent.agents.data.text2sql.executor import DIALECT_NAMES, DS_TYPES
from .comparator import CompareReport, skew_side_verdict
from .i18n import dc
from .presets import ConnectionPresetsStore
from .templates_store import ComparisonTemplatesStore

# ---------------------------------------------------------------------------
# Matplotlib import (lazy — only used for trend charts)
# ---------------------------------------------------------------------------

def _get_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc_html(s: str) -> str:
    # quote=False + manual &quot;: escape & < > " but keep ' intact —
    # several cards embed single-quoted JS in onclick attributes.
    return html.escape(str(s), quote=False).replace('"', "&quot;")


_ERR_ESSENCE_RES = (
    # HiveServer2 thrift blobs: the one useful sentence hides in errorMessage=
    re.compile(r"errorMessage=[\"'](.+?)[\"']\)?,?\s*(?:operationHandle|$)", re.S),
    # driver exceptions that lead with the interesting line
    re.compile(r"((?:Parse|Semantic|Operational|Programming)(?:Exception|Error)[^\n]{0,200})"),
)


def _error_html(lang: str, exc: Exception) -> str:
    """Error card: lead with the one sentence that matters, collapse the
    raw exception behind <details> — a full TExecuteStatementResp thrift
    dump was unreadable (three separate user reports)."""
    raw = str(exc)
    essence = ""
    for pat in _ERR_ESSENCE_RES:
        m = pat.search(raw)
        if m:
            essence = m.group(1).strip()
            break
    head = essence if essence and essence != raw.strip() else raw
    html = (f'<div style="color:#dc2626;font-weight:600;">'
            f'❌ {dc(lang, "dc_error")}: {_esc_html(head[:500])}</div>')
    if essence and essence != raw.strip():
        html += (f'<details style="margin-top:6px;"><summary style="color:#6b7280;'
                 f'font-size:12px;cursor:pointer;">{_esc_html(type(exc).__name__)}'
                 f' — raw</summary><pre style="white-space:pre-wrap;font-size:11px;'
                 f'color:#6b7280;">{_esc_html(raw[:4000])}</pre></details>')
    return html


_log = logging.getLogger(__name__)

# Tunable limits (previously scattered magic numbers)
_SAMPLE_LIMIT = 100          # rows sampled per side
_STRATIFIED_PER_GROUP = 10   # rows per stratum in stratified sampling
_SKEW_MAX_COLUMNS = 10       # columns analysed for skew
_SKEW_MAX_ROWS = 50          # top-N frequency rows fetched per column
_MAX_AGG_COLUMNS = 20        # numeric columns per aggregate comparison
_MAX_REPORT_FILES = 50       # saved reports listed in dropdowns
_SUMMARY_MAX_ITEMS = 10      # items shown in report summary sections
_DELTA_WARN_PCT = 10         # row-count delta % below which it's a warning
_DEFAULT_SCHEDULE_MIN = 15   # default scheduled-comparison interval (minutes)

_DS_CHOICES = [DIALECT_NAMES[d] for d in DS_TYPES]
_DS_LABEL_TO_KEY = {v: k for k, v in DIALECT_NAMES.items()}
_NEEDS_AUTH = frozenset({"mysql", "sqlserver", "sparksql", "clickhouse", "doris", "postgresql"})
_NEEDS_HOST = frozenset(DS_TYPES) - {"flinksql", "sqlite"}

_DDL_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE"
    r"|MERGE|CALL|UNION|SET|LOAD|COPY|RENAME)\b"
    r"|INTO\s+OUTFILE",
    re.IGNORECASE,
)

_REPORTS_DIR = Path(os.getenv(
    "DC_REPORTS_DIR", str(Path.home() / ".seatunnel-agent" / "reports")))
_PRESETS_STORE = ConnectionPresetsStore()
_TEMPLATES_STORE = ComparisonTemplatesStore()
_SAMPLE_STRATEGIES = ["TOP N", "RANDOM", "STRATIFIED"]

# Tunable limits (override via environment)
_DEFAULT_LANG = os.getenv("SEATUNNEL_UI_LANG", "en")
_CHECKSUM_MAX_ROWS = int(os.getenv("DC_CHECKSUM_MAX_ROWS", "100"))
_PARTITION_MAX_ROWS = int(os.getenv("DC_PARTITION_MAX_ROWS", "1000"))
_INCREMENTAL_LIMIT = int(os.getenv("DC_INCREMENTAL_LIMIT", "1000"))
_WEBHOOK_TIMEOUT = int(os.getenv("DC_WEBHOOK_TIMEOUT", "10"))
_LIST_LIMIT = int(os.getenv("DC_LIST_LIMIT", "50"))

_TH = 'style="text-align:left;padding:4px 6px;font-size:11px;border-bottom:1px solid #e5e7eb;"'
_TD = 'style="padding:4px 6px;font-size:11px;border-bottom:1px solid #f3f4f6;"'


def _details_card(summary_html: str, body_html: str, border_color: str = "#e0e7ff") -> str:
    return (
        f'<details open style="border:1px solid {border_color};border-radius:8px;'
        f'padding:10px;background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;cursor:pointer;">'
        f'{summary_html}</summary>{body_html}</details>'
    )


def _build_webhook_summary(report: CompareReport) -> dict:
    """Extract top-10 schema diffs and agg mismatches as structured data."""
    summary: dict[str, Any] = {}
    if report.schema and report.schema.has_changes:
        summary["schema_diffs"] = [
            {"column": it.column, "status": it.status,
             "type_a": it.type_a, "type_b": it.type_b}
            for it in report.schema.items[:_SUMMARY_MAX_ITEMS]
        ]
    if report.aggregate and report.aggregate.mismatches > 0:
        summary["agg_mismatches"] = [
            {"column": it.column, "metric": it.metric,
             "value_a": it.value_a, "value_b": it.value_b}
            for it in report.aggregate.items[:_SUMMARY_MAX_ITEMS]
            if not it.match
        ][:_SUMMARY_MAX_ITEMS]
    if report.skew is not None and report.skew.items:
        verdict, v_cols = skew_side_verdict(report.skew)
        summary["skew"] = {
            "verdict": verdict,
            "columns": v_cols[:_SUMMARY_MAX_ITEMS],
            "top1_max": max(max(it.top1_pct_a, it.top1_pct_b)
                            for it in report.skew.items),
            "gini_max": max(max(it.gini_a, it.gini_b)
                            for it in report.skew.items),
        }
    return summary


def _send_webhook(url: str, payload: dict) -> tuple[bool, str]:
    """POST JSON payload to a webhook URL. Returns (success, message)."""
    import urllib.request
    import urllib.error
    data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT) as resp:
            return True, f"{resp.status}"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return False, str(exc)


def _validate_where(clause: str, lang: str) -> tuple[bool, str]:
    """Validate a WHERE clause — reject DDL keywords."""
    if not clause.strip():
        return True, ""
    m = _DDL_KEYWORDS.search(clause)
    if m:
        return False, dc(lang, "dc_where_invalid").format(kw=m.group(0))
    return True, ""


def _with_validation(holder, holder_lock, fn):
    """Wrap a compare callback with connection/table checks and error handling."""
    def wrapper(*args):
        lang_val = args[2] if len(args) > 2 else "en"
        with holder_lock:
            if holder.get("executor_a") is None or holder.get("executor_b") is None:
                return dc(lang_val, "dc_connect_both")
        table_a = args[0] if len(args) > 0 else ""
        table_b = args[1] if len(args) > 1 else ""
        if not table_a or not table_b:
            return dc(lang_val, "dc_select_tables")
        t0 = time.perf_counter()
        try:
            result = fn(*args)
            _log.info("%s ok: tables=%r/%r elapsed=%dms", fn.__name__,
                      table_a, table_b, int((time.perf_counter() - t0) * 1000))
            return result
        except Exception as e:
            _log.exception("%s failed: tables=%r/%r elapsed=%dms", fn.__name__,
                           table_a, table_b, int((time.perf_counter() - t0) * 1000))
            return _error_html(lang_val, e)
    return wrapper
