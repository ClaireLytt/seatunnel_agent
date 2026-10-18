"""REST API for Data Comparison report persistence (ticket 07).

Save / list / load saved reports, report-vs-report diff, CSV + Excel
export, and the standalone HTML report view. Own router included by
``api.py``; imports Gradio-free modules only (registry / models /
comparator / ui_cards / ui_reports) — never ``ui.py``.

The legacy closures live in ``ui.py`` (_save_report / _list_reports /
_load_report / _compare_reports_fn / _export_csv / _export_excel /
_build_report_page); exports reuse ``ui_reports`` verbatim and
rendering reuses the pure ``ui_cards`` builders.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from seatunnel_agent.agents.data.data_comparison.comparator import (
    CompareReport,
    diff_reports,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import (
    SessionState,
    get_registry,
)
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_aggregate_card,
    build_batch_count_card,
    build_checksum_card,
    build_chunked_card,
    build_count_card,
    build_custom_agg_card,
    build_keyed_diff_card,
    build_partition_card,
    build_profile_card,
    build_report_diff_card,
    build_schema_diff_card,
    build_skew_card,
    build_standalone_report,
)
from seatunnel_agent.agents.data.data_comparison.ui_reports import (
    _export_report_csv,
    _export_report_excel,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _MAX_REPORT_FILES,
    _REPORTS_DIR,
    _esc_html,
)

# No prefix of its own: api.py includes this router under /api/datacompare.
router = APIRouter(tags=["datacompare-reports"])


def _get_session(session_id: str) -> SessionState:
    session = get_registry().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return session


def _snap_report(session: SessionState) -> CompareReport:
    """The session's last report, or 409 when none exists yet."""
    with session.lock:
        report = session.last_report
    if not report:
        raise HTTPException(status_code=409, detail="no report yet")
    assert isinstance(report, CompareReport)
    return report


def _report_path(name: str) -> Path:
    """Resolve a saved-report filename, refusing anything path-like."""
    if (not re.fullmatch(r"compare_[^/\\]*\.json", name)
            or ".." in name):
        raise HTTPException(status_code=404, detail="unknown report")
    path = _REPORTS_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="unknown report")
    return path


def _read_report(name: str) -> CompareReport:
    with open(_report_path(name), encoding="utf-8") as f:
        return CompareReport.from_dict(json.load(f))


# ── save / list / load (legacy ui.py _save_report/_list_reports/_load_report) ──


class ReportSaveRequest(BaseModel):
    session_id: str
    table_a: str = ""
    table_b: str = ""
    lang: str = "en"


@router.post("/reports")
def save_report(req: ReportSaveRequest) -> dict[str, Any]:
    """Persist the session's last report as compare_<a>_vs_<b>_<ts>.json."""
    session = _get_session(req.session_id)
    with session.lock:
        report = session.last_report
    if not report:
        return {"ok": False, "error": dc(req.lang, "dc_no_report")}
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def _safe(name: str) -> str:
        return re.sub(r"[^0-9A-Za-z_\-一-鿿]", "_", str(name or ""))[:40]

    # table names in the filename so the load dropdown is findable
    pair = (f"{_safe(req.table_a)}_vs_{_safe(req.table_b)}_"
            if req.table_a and req.table_b else "")
    fpath = _REPORTS_DIR / f"compare_{pair}{ts}.json"
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    return {"ok": True, "filename": fpath.name}


@router.get("/reports")
def list_reports() -> dict[str, list[str]]:
    """Saved report filenames, newest first (cap: legacy dropdown limit)."""
    if not _REPORTS_DIR.is_dir():
        return {"files": []}
    files = sorted(_REPORTS_DIR.glob("compare_*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    return {"files": [f.name for f in files[:_MAX_REPORT_FILES]]}


@router.get("/reports/{name}")
def load_report(name: str, session_id: str, lang: str = "en") -> dict[str, str]:
    """Load a saved report into the session and render its cards."""
    session = _get_session(session_id)
    report = _read_report(name)
    with session.lock:
        session.last_report = report

    parts: list[str] = [
        f'<div style="color:#16a34a;font-weight:600;margin-bottom:8px;">'
        f'✅ {dc(lang, "dc_loaded")} — {_esc_html(name)}</div>'
    ]
    # same card order as the legacy _load_report (ui.py)
    if report.schema is not None:
        parts.append(build_schema_diff_card(report.schema, lang))
    if report.row_count is not None:
        parts.append(build_count_card(report.row_count, lang))
    if report.aggregate is not None:
        parts.append(build_aggregate_card(report.aggregate, lang))
    if report.profile is not None:
        parts.append(build_profile_card(report.profile, lang))
    if report.skew is not None:
        parts.append(build_skew_card(report.skew, lang))
    if report.checksum is not None:
        parts.append(build_checksum_card(report.checksum, lang))
    if report.partition is not None:
        parts.append(build_partition_card(report.partition, lang))
    if report.custom_agg is not None:
        parts.append(build_custom_agg_card(report.custom_agg, lang))
    if report.chunked is not None:
        parts.append(build_chunked_card(report.chunked, lang))
    if report.keyed_diff is not None:
        parts.append(build_keyed_diff_card(report.keyed_diff, lang))
    if report.batch_counts is not None:
        parts.append(build_batch_count_card(report.batch_counts, lang))
    return {"html": "\n".join(parts)}


# ── report-vs-report diff (legacy _compare_reports_fn ui.py:1353) ──


class ReportDiffRequest(BaseModel):
    old: str
    new: str
    lang: str = "en"


@router.post("/reports/diff")
def report_diff(req: ReportDiffRequest) -> dict[str, str]:
    """Diff two saved reports; renders the legacy diff card."""
    old_report = _read_report(req.old)
    new_report = _read_report(req.new)
    rdiff = diff_reports(old_report, new_report)
    return {"html": build_report_diff_card(rdiff, req.lang)}


# ── exports (legacy _export_csv/_export_excel + ui_reports helpers) ──


@router.get("/export/csv")
def export_csv(session_id: str, lang: str = "en") -> FileResponse:
    """Multi-section CSV of the session's last report."""
    report = _snap_report(_get_session(session_id))
    path = Path(_export_report_csv(report))
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("/export/xlsx")
def export_xlsx(session_id: str, lang: str = "en") -> FileResponse:
    """Multi-sheet Excel workbook of the session's last report."""
    report = _snap_report(_get_session(session_id))
    path = Path(_export_report_excel(report))
    return FileResponse(
        path,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"),
        filename=path.name,
    )


# ── standalone HTML view (legacy _build_report_page + window.open hack) ──


@router.get("/report/standalone")
def standalone_report(session_id: str, lang: str = "en") -> HTMLResponse:
    """Full standalone report page — the React page links here (_blank)."""
    report = _snap_report(_get_session(session_id))
    return HTMLResponse(build_standalone_report(report, lang))
