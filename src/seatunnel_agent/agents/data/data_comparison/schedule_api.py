"""REST API for scheduled comparisons and history trends (ticket 09).

Schedule start/stop/status port the legacy ``ui.py`` closures
(``_schedule_start``/``_schedule_stop``/``_schedule_tick``,
ui.py:1248/1273/748): a daemon ``threading.Timer`` keyed to the session
registry re-runs compare-all every N minutes, saves the report and
re-arms itself. ``GET /trends`` replaces the matplotlib figure with the
raw ``build_trend_data`` series as JSON (recharts renders client-side
per spec); the alert card stays server-rendered HTML.

Intentional deviation from legacy: the legacy tick called
``_save_report(lang_val)`` with the wrong arity, so scheduled runs never
actually persisted their report (the TypeError was swallowed into
``schedule_last_error``). Here the tick saves via the ticket-07 save
path with the full table_a/table_b/lang arguments, as the spec requires.

Own router included by ``api.py``; imports Gradio-free modules only.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from seatunnel_agent.agents.data.data_comparison import reports_api
from seatunnel_agent.agents.data.data_comparison.comparator import (
    build_trend_data,
    check_trend_alerts,
    parse_alert_rules,
)
from seatunnel_agent.agents.data.data_comparison.compound import (
    CompoundRequest,
    compare_all_run,
    release_run,
    try_acquire_run,
)
from seatunnel_agent.agents.data.data_comparison.deps import (
    get_session_or_404,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import SessionState
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_trend_alert_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _DEFAULT_SCHEDULE_MIN,
    _log,
    _send_webhook,
)

# No prefix of its own: api.py includes this router under /api/datacompare.
router = APIRouter(tags=["datacompare-schedule"])


class ScheduleStartRequest(CompoundRequest):
    """Compare-all params (incl. webhook fields) plus the interval."""

    interval: str = "15"


class ScheduleStopRequest(BaseModel):
    session_id: str
    lang: str = "en"


def _noop_progress(value: float, desc: str = "") -> None:
    """Scheduled runs have no progress consumer."""


def _reschedule(session: SessionState, interval_min: int) -> None:
    """Arm the next tick, unless the schedule was stopped meanwhile."""
    with session.lock:
        if not session.schedule_active:
            return
        timer = threading.Timer(float(interval_min) * 60,
                                run_schedule_tick, args=(session,))
        timer.daemon = True
        session.schedule_timer = timer
    timer.start()


def run_schedule_tick(session: SessionState) -> None:
    """One scheduled run: compare-all, save the report, re-arm the timer.

    Port of the legacy ``_schedule_tick`` (ui.py:748) — minus its
    ``_save_report(lang_val)`` arity bug (see module docstring).
    """
    with session.lock:
        req = session.schedule_request
        interval_min = session.schedule_interval
    if req is None:  # stopped and cleared between arm and fire
        return
    assert isinstance(req, CompoundRequest)
    # Same per-session guard as the compound endpoints (legacy single-run
    # semantics): skip this tick when a manual run is in flight.
    if not try_acquire_run(session.session_id):
        with session.lock:
            session.schedule_last_error = "busy"
        _reschedule(session, interval_min)
        return
    try:
        with session.lock:
            report_before = session.last_report
        compare_all_run(session, req, _noop_progress)
        with session.lock:
            report_after = session.last_report
        if report_after is None or report_after is report_before:
            # a guard message (not connected / bad table) came back as
            # html; there is no fresh report to persist
            raise RuntimeError("comparison produced no report")
        saved = reports_api.save_report(reports_api.ReportSaveRequest(
            session_id=session.session_id, table_a=req.table_a,
            table_b=req.table_b, lang=req.lang))
        if not saved.get("ok"):
            raise RuntimeError(str(saved.get("error") or "report not saved"))
        with session.lock:
            session.schedule_last_run = datetime.now(
                timezone.utc).strftime("%H:%M:%S")
            session.schedule_last_error = None
    except Exception as exc:
        _log.warning("Scheduled comparison failed", exc_info=True)
        with session.lock:
            session.schedule_last_error = str(exc)
        if req.webhook_url.strip():
            _send_webhook(req.webhook_url.strip(), {
                "event": "scheduled_comparison_error",
                "table_a": req.table_a, "table_b": req.table_b,
                "error": str(exc),
            })
    finally:
        release_run(session.session_id)
    _reschedule(session, interval_min)


@router.post("/schedule/start")
def schedule_start(req: ScheduleStartRequest) -> dict[str, Any]:
    """Arm the per-session comparison timer (legacy _schedule_start)."""
    session = get_session_or_404(req.session_id)
    if not req.table_a or not req.table_b:
        return {"ok": False, "active": False,
                "message": dc(req.lang, "dc_select_tables")}
    try:
        interval_min = int(req.interval)
    except (TypeError, ValueError):
        interval_min = _DEFAULT_SCHEDULE_MIN
    interval_min = max(1, interval_min)
    with session.lock:
        if session.schedule_active:
            running = session.schedule_interval or interval_min
            return {"ok": True, "active": True,
                    "message": dc(req.lang,
                                  "dc_schedule_running").format(m=running)}
        session.schedule_active = True
        session.schedule_interval = interval_min
        session.schedule_request = req
    _reschedule(session, interval_min)
    message = dc(req.lang, "dc_schedule_running").format(m=interval_min)
    return {"ok": True, "active": True, "message": f"✅ {message}"}


@router.post("/schedule/stop")
def schedule_stop(req: ScheduleStopRequest) -> dict[str, Any]:
    """Cancel the timer and deactivate (legacy _schedule_stop)."""
    session = get_session_or_404(req.session_id)
    with session.lock:
        session.schedule_active = False
        session.schedule_request = None
        timer = session.schedule_timer
        session.schedule_timer = None
    if timer is not None:
        timer.cancel()
    return {"ok": True, "active": False,
            "message": dc(req.lang, "dc_schedule_stopped")}


@router.get("/schedule/status")
def schedule_status(session_id: str) -> dict[str, Any]:
    """Live schedule state (new endpoint; legacy only had status strings)."""
    session = get_session_or_404(session_id)
    with session.lock:
        return {
            "active": session.schedule_active,
            "interval": session.schedule_interval,
            "last_run": session.schedule_last_run,
            "last_error": session.schedule_last_error,
        }


@router.get("/trends")
def trends(lang: str = "en", alert_rules: str = "") -> dict[str, Any]:
    """Trend series as JSON + the server-rendered alert card.

    Replaces the legacy matplotlib PNG (_show_trend, ui.py:818): the
    React page draws the chart from ``entries`` with recharts.
    """
    entries = build_trend_data(reports_api._REPORTS_DIR)
    alerts_html = ""
    if alert_rules.strip():
        rules = parse_alert_rules(alert_rules)
        if rules:
            alerts_html = build_trend_alert_card(
                check_trend_alerts(entries, rules), lang)
    return {"entries": entries, "alerts_html": alerts_html}
