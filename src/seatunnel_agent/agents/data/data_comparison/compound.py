"""Compound comparison actions for the REST API (ticket 04).

Gradio-free ports of the heavy ``ui.py`` closures — compare-all,
batch count, batch full and column profile. The three long-running
actions stream Server-Sent Events (seatunnel ``api.py`` precedent:
worker thread pushes into a ``queue.Queue``, the response generator
drains it) with frames::

    {"event": "progress", "value": 0.4, "desc": "Comparing..."}
    {"event": "done", "html": "<...result cards...>"}

A per-session running flag rejects concurrent compound runs with
HTTP 409 (double-trigger guard; seatunnel 409-when-running precedent).

Compare-all runs the always-on stages (schema, count, sample,
aggregate, profile) plus — when their option strings are set — the
optional skew / checksum / partition / custom-aggregate stages from
``features.py`` (ticket 06), and the webhook.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from seatunnel_agent.agents.data.data_comparison import actions, features
from seatunnel_agent.agents.data.data_comparison.comparator import (
    BatchFullItem,
    CompareReport,
    KeyedDiffResult,
    RowCountResult,
    build_count_sql,
    build_row_count_result,
    find_common_tables,
    parse_threshold,
    run_parallel,
)
from seatunnel_agent.agents.data.data_comparison.deps import (
    OptionsRequest,
    get_session_or_404,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import SessionState
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_batch_count_card,
    build_batch_full_card,
    build_count_card,
    build_summary_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _build_webhook_summary,
    _error_html,
    _log,
    _send_webhook,
    _validate_where,
    _with_validation,
)

router = APIRouter()

# Session ids with a compound run in flight (double-trigger guard).
# The scheduled tick (schedule_api.run_schedule_tick) acquires the same
# guard via try_acquire_run/release_run — legacy single-run semantics.
_RUNNING: set[str] = set()
_RUNNING_LOCK = threading.Lock()


def try_acquire_run(session_id: str) -> bool:
    """Take the per-session running flag; False when a run is in flight."""
    with _RUNNING_LOCK:
        if session_id in _RUNNING:
            return False
        _RUNNING.add(session_id)
        return True


def release_run(session_id: str) -> None:
    """Release the per-session running flag."""
    with _RUNNING_LOCK:
        _RUNNING.discard(session_id)


ProgressFn = Callable[[float, str], None]


class CompoundRequest(OptionsRequest):
    """Request body shared by the compound actions.

    The shared options base rides on every action; webhook fields are
    compare-all only.
    """

    webhook_url: str = ""
    notify_on_fail: bool = False
    # optional compare-all stages (feature accordion fields, ticket 06)
    skew_columns: str = ""
    checksum_columns: str = ""
    partition_col: str = ""
    expressions: str = ""


# ── profile (not actually slow — plain JSON like the core actions) ──


def profile_inner(
    session: SessionState, table_a: str, table_b: str, lang_val: str,
    where_val: str = "",
) -> tuple[Any, str]:
    """Column profile comparison over shared columns (features.py port)."""
    return features.profile_inner(session, table_a, table_b, lang_val,
                                  where_val)


def compare_profile(session: SessionState, table_a: str, table_b: str,
                    lang_val: str = "en", where_val: str = "") -> str:
    """Validated profile action (guards + error card + report storage)."""
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = profile_inner(session, ta, tb, lv, where_val)
        actions.store_partial(session, "profile", result)
        return html
    _fn.__name__ = "compare_profile"
    return _with_validation(session, _fn)(table_a, table_b, lang_val)


@router.post("/compare/profile")
def compare_profile_endpoint(req: CompoundRequest) -> dict[str, str]:
    """Column profile card (HTML fragment; guards return their message)."""
    session = get_session_or_404(req.session_id)
    return {"html": compare_profile(
        session, req.table_a, req.table_b, req.lang, req.where)}


# ── compare-all (always-on stages + webhook; port of ui._compare_all) ──


def compare_all_run(session: SessionState, req: CompoundRequest,
                    progress: ProgressFn) -> str:
    """Full comparison; returns the concatenated result-card html."""
    table_a, table_b, lang_val = req.table_a, req.table_b, req.lang
    where_val = req.where
    _log.info("compare_all start: tables=%r/%r lang=%r",
              table_a, table_b, lang_val)
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
    if not table_a or not table_b:
        return dc(lang_val, "dc_select_tables")
    ok, msg = _validate_where(where_val, lang_val)
    if not ok:
        return msg

    threshold = parse_threshold(req.threshold)

    try:
        t0 = time.perf_counter()
        ex_a, ex_b = actions.snap_executors(session)

        progress(0.1, dc(lang_val, "dc_running"))
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(table_a),
            lambda: ex_b.describe_table(table_b),
        )

        progress(0.25, dc(lang_val, "dc_running"))
        schema_result, schema_html = actions.schema_inner(
            session, table_a, table_b, lang_val, where_val, desc_a, desc_b)

        progress(0.4, dc(lang_val, "dc_running"))
        count_result, _ = actions.count_inner(
            session, table_a, table_b, lang_val, where_val)
        count_html = build_count_card(count_result, lang_val, threshold)

        progress(0.55, dc(lang_val, "dc_running"))
        sample_result, sample_html = actions.sample_inner(
            session, table_a, table_b, lang_val, where_val,
            req.key_columns, req.strategy, req.column_mapping,
            req.masking, req.stratified_col)

        progress(0.7, dc(lang_val, "dc_running"))
        agg_result, agg_html = actions.agg_inner(
            session, table_a, table_b, lang_val, where_val, desc_a, desc_b)

        progress(0.8, dc(lang_val, "dc_running"))
        profile_result, profile_html = profile_inner(
            session, table_a, table_b, lang_val, where_val)

        # optional stages — run only when their option strings are set
        skew_result = None
        skew_html = ""
        if req.skew_columns.strip():
            progress(0.84, dc(lang_val, "dc_running"))
            skew_result, skew_html = features.skew_inner(
                session, table_a, table_b, lang_val, where_val,
                req.skew_columns)

        checksum_result = None
        checksum_html = ""
        if req.checksum_columns.strip():
            progress(0.88, dc(lang_val, "dc_running"))
            checksum_result, checksum_html = features.checksum_inner(
                session, table_a, table_b, lang_val, where_val,
                req.checksum_columns)

        partition_result = None
        partition_html = ""
        if req.partition_col.strip():
            progress(0.92, dc(lang_val, "dc_running"))
            partition_result, partition_html = features.partition_inner(
                session, table_a, table_b, lang_val, where_val,
                req.partition_col)

        custom_agg_result = None
        custom_agg_html = ""
        if req.expressions.strip():
            progress(0.96, dc(lang_val, "dc_running"))
            custom_agg_result, custom_agg_html = features.custom_agg_inner(
                session, table_a, table_b, lang_val, where_val,
                req.expressions)

        elapsed = int((time.perf_counter() - t0) * 1000)

        keyed_diff = (sample_result
                      if isinstance(sample_result, KeyedDiffResult) else None)
        sample_for_report = None if keyed_diff else sample_result

        report = CompareReport(
            schema=schema_result,
            row_count=count_result,
            sample=sample_for_report,
            aggregate=agg_result,
            profile=profile_result,
            keyed_diff=keyed_diff,
            skew=skew_result,
            checksum=checksum_result,
            partition=partition_result,
            custom_agg=custom_agg_result,
            elapsed_ms=elapsed,
        )
        with session.lock:
            session.last_report = report

        has_diffs = bool(
            (schema_result and schema_result.has_changes)
            or (count_result and count_result.delta != 0)
            or (agg_result and agg_result.mismatches > 0)
            or (checksum_result and checksum_result.mismatch_count > 0)
            or (partition_result and partition_result.total_delta != 0)
            or (custom_agg_result and custom_agg_result.mismatches > 0)
        )

        webhook_url = req.webhook_url.strip()
        if webhook_url and not (req.notify_on_fail and not has_diffs):
            payload = {
                "table_a": table_a, "table_b": table_b,
                "has_diffs": has_diffs,
                "elapsed_ms": elapsed,
                "row_count_delta": count_result.delta if count_result else 0,
                "schema_changes": (len(schema_result.items)
                                   if schema_result and schema_result.has_changes
                                   else 0),
                "aggregate_mismatches": (agg_result.mismatches
                                         if agg_result else 0),
                "checksum_mismatches": (checksum_result.mismatch_count
                                        if checksum_result else 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "count_a": count_result.count_a if count_result else 0,
                    "count_b": count_result.count_b if count_result else 0,
                    "delta_pct": count_result.delta_pct if count_result else 0,
                },
                "report_summary": _build_webhook_summary(report),
            }
            threading.Thread(target=_send_webhook,
                             args=(webhook_url, payload),
                             daemon=True).start()

        progress(1.0, "Done")
        html = (build_summary_card(report, lang_val) + schema_html
                + count_html + sample_html + agg_html + profile_html
                + skew_html + checksum_html + partition_html
                + custom_agg_html)
        _log.info("compare_all done: tables=%r/%r elapsed=%dms html=%d chars",
                  table_a, table_b, elapsed, len(html))
        return html
    except Exception as e:
        _log.exception("compare_all failed: tables=%r/%r", table_a, table_b)
        if req.webhook_url.strip():
            threading.Thread(
                target=_send_webhook,
                args=(req.webhook_url.strip(),
                      {"error": str(e), "table_a": table_a,
                       "table_b": table_b}),
                daemon=True,
            ).start()
        return _error_html(lang_val, e)


# ── batch count / batch full (ports of ui._batch_count/_batch_full) ──


def batch_count_run(session: SessionState, req: CompoundRequest,
                    progress: ProgressFn) -> str:
    lang_val, where_val = req.lang, req.where
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
        tables_a = list(session.tables_a)
        tables_b = list(session.tables_b)
        ex_a, ex_b = session.executor_a, session.executor_b

    ok, msg = _validate_where(where_val, lang_val)
    if not ok:
        return msg

    try:
        pairs = find_common_tables(tables_a, tables_b)
        if not pairs:
            return _no_common_card(lang_val, "dc_batch_result")

        results: list[RowCountResult] = []
        total = len(pairs)
        for idx, (ta, tb) in enumerate(pairs):
            progress((idx + 1) / total,
                     dc(lang_val, "dc_comparing_table").format(name=ta))
            sql_a = build_count_sql(ta, where_val)
            sql_b = build_count_sql(tb, where_val)
            ra, rb = run_parallel(
                lambda: ex_a.run(sql_a, max_rows=1),
                lambda: ex_b.run(sql_b, max_rows=1),
            )
            ca = int(ra.rows[0][0]) if ra.rows else 0
            cb = int(rb.rows[0][0]) if rb.rows else 0
            results.append(build_row_count_result(ta, ca, tb, cb))

        actions.store_partial(session, "batch_counts", results)
        return build_batch_count_card(results, lang_val)
    except Exception as e:
        return _error_html(lang_val, e)


def batch_full_run(session: SessionState, req: CompoundRequest,
                   progress: ProgressFn) -> str:
    lang_val, where_val = req.lang, req.where
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
        tables_a = list(session.tables_a)
        tables_b = list(session.tables_b)

    ok, msg = _validate_where(where_val, lang_val)
    if not ok:
        return msg

    threshold = parse_threshold(req.threshold)

    try:
        pairs = find_common_tables(tables_a, tables_b)
        if not pairs:
            return _no_common_card(lang_val, "dc_batch_full_result")

        items: list[BatchFullItem] = []
        total = len(pairs)
        for idx, (ta, tb) in enumerate(pairs):
            progress((idx + 1) / total,
                     dc(lang_val, "dc_comparing_table").format(name=ta))
            schema_r: Any = None
            count_r: Any = None
            agg_r: Any = None
            try:
                schema_r, _ = actions.schema_inner(
                    session, ta, tb, lang_val, where_val)
            except Exception:
                schema_r = None
            try:
                count_r, _ = actions.count_inner(
                    session, ta, tb, lang_val, where_val)
            except Exception:
                count_r = None
            try:
                agg_r, _ = actions.agg_inner(
                    session, ta, tb, lang_val, where_val)
            except Exception:
                agg_r = None

            has_diffs = bool(
                (schema_r and schema_r.has_changes)
                or (count_r and count_r.delta != 0)
                or (agg_r and agg_r.mismatches > 0)
            )
            items.append(BatchFullItem(ta, tb, schema_r, count_r, agg_r,
                                       has_diffs))

        actions.store_partial(session, "batch_full", items)
        return build_batch_full_card(items, lang_val, threshold)
    except Exception as e:
        return _error_html(lang_val, e)


def _no_common_card(lang_val: str, title_key: str) -> str:
    return (
        '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
        'background:#f9fafb;margin-bottom:8px;">'
        f'<b style="color:#6b7280;">{dc(lang_val, title_key)}</b> — '
        f'{dc(lang_val, "dc_no_common")}</div>'
    )


# ── SSE plumbing (seatunnel queue+worker precedent) ──────────────────


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _stream_run(
    req: CompoundRequest,
    run: Callable[[SessionState, CompoundRequest, ProgressFn], str],
) -> StreamingResponse:
    """Run *run* in a worker thread, streaming progress + done frames.

    Acquires the per-session running flag before the stream starts so a
    second trigger gets an immediate HTTP 409.
    """
    session = get_session_or_404(req.session_id)

    if not try_acquire_run(req.session_id):
        raise HTTPException(status_code=409,
                            detail="a compound run is already in progress")

    q: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def progress(value: float, desc: str = "") -> None:
        q.put({"event": "progress", "value": value, "desc": desc})

    def work() -> None:
        try:
            html = run(session, req, progress)
        except Exception as e:  # pragma: no cover — run fns catch their own
            html = _error_html(req.lang, e)
        finally:
            release_run(req.session_id)
        q.put({"event": "done", "html": html})
        q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen() -> Iterator[str]:
        while True:
            item = q.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/compare/all")
def compare_all_endpoint(req: CompoundRequest) -> StreamingResponse:
    """Full comparison of the selected pair, streamed as SSE."""
    return _stream_run(req, compare_all_run)


@router.post("/compare/batch-count")
def batch_count_endpoint(req: CompoundRequest) -> StreamingResponse:
    """Row-count comparison over every common table, streamed as SSE."""
    return _stream_run(req, batch_count_run)


@router.post("/compare/batch-full")
def batch_full_endpoint(req: CompoundRequest) -> StreamingResponse:
    """Schema+count+aggregate over every common table, streamed as SSE."""
    return _stream_run(req, batch_full_run)
