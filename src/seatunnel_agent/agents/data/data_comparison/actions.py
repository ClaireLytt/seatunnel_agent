"""Gradio-free core comparison actions (schema / count / sample / aggregate).

Extracted from the ``render_data_comparison_page`` closures in ``ui.py`` so
the REST layer (``api.py``) and the legacy Gradio page share one
implementation. Every function takes the per-session
:class:`~.registry.SessionState` explicitly instead of closing over it.

Two layers per action:

- ``*_inner(session, ...) -> (result, html)`` — raw comparison, no
  validation; also used by compound actions (compare-all) in ``ui.py``.
- ``compare_*(session, ...) -> html`` — the user-facing action: WHERE
  validation, connection/table guards and error-card handling via
  ``ui_shared._with_validation``, plus storing the partial result into
  the session's ``last_report``.
"""

from __future__ import annotations

from typing import Any

from seatunnel_agent.agents.data.data_comparison.comparator import (
    AggregateResult,
    CompareReport,
    KeyedDiffResult,
    apply_column_mapping,
    build_aggregate_sql,
    build_count_sql,
    build_random_sample_sql,
    build_row_count_result,
    build_sample_sql,
    build_stratified_sample_sql,
    compare_aggregates,
    compare_schemas,
    detect_sensitive_columns,
    diff_by_key,
    is_numeric_type,
    mask_rows,
    parse_column_mapping,
    parse_threshold,
    run_parallel,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import SessionState
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_aggregate_card,
    build_count_card,
    build_keyed_diff_card,
    build_sample_diff_card,
    build_schema_diff_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _SAMPLE_LIMIT,
    _STRATIFIED_PER_GROUP,
    _esc_html,
    _log,
    _validate_where,
    _with_validation,
)
from seatunnel_agent.agents.data.text2sql.differ import diff_results


def snap_executors(session: SessionState) -> tuple[Any, Any]:
    """Snapshot both executors under the session lock."""
    with session.lock:
        return session.executor_a, session.executor_b


def store_partial(session: SessionState, key: str, value: Any) -> None:
    """Store a single comparison result into the session's report."""
    with session.lock:
        if session.last_report is None:
            session.last_report = CompareReport()
        setattr(session.last_report, key, value)


# ── Inner comparison logic (no validation — used by single + all) ──


def schema_inner(
    session: SessionState, table_a: str, table_b: str, lang_val: str,
    where_val: str = "", desc_a: Any = None, desc_b: Any = None,
) -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    if desc_a is None and desc_b is None:
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(table_a),
            lambda: ex_b.describe_table(table_b),
        )
    else:
        if desc_a is None:
            desc_a = ex_a.describe_table(table_a)
        if desc_b is None:
            desc_b = ex_b.describe_table(table_b)
    cols_a = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
    cols_b = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
    result = compare_schemas(cols_a, cols_b, table_a, table_b)
    return result, build_schema_diff_card(result, lang_val)


def count_inner(
    session: SessionState, table_a: str, table_b: str, lang_val: str,
    where_val: str = "",
) -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    sql_a = build_count_sql(table_a, where_val)
    sql_b = build_count_sql(table_b, where_val)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=1),
        lambda: ex_b.run(sql_b, max_rows=1),
    )
    ca = int(ra.rows[0][0]) if ra.rows else 0
    cb = int(rb.rows[0][0]) if rb.rows else 0
    result = build_row_count_result(table_a, ca, table_b, cb)
    return result, build_count_card(result, lang_val)


def sample_inner(
    session: SessionState, table_a: str, table_b: str, lang_val: str,
    where_val: str = "", key_cols_str: str = "", strategy: str = "TOP N",
    col_mapping_str: str = "", masking_on: bool = True,
    stratified_col: str = "",
) -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    limit = _SAMPLE_LIMIT
    stratified_col = stratified_col or ""  # hidden textbox submits None
    if strategy == "STRATIFIED" and stratified_col.strip():
        sql_a = build_stratified_sample_sql(table_a, stratified_col.strip(),
                                            _STRATIFIED_PER_GROUP,
                                            ex_a.config.ds_type, where_val)
        sql_b = build_stratified_sample_sql(table_b, stratified_col.strip(),
                                            _STRATIFIED_PER_GROUP,
                                            ex_b.config.ds_type, where_val)
    elif strategy == "RANDOM":
        sql_a = build_random_sample_sql(table_a, limit, ex_a.config.ds_type, where_val)
        sql_b = build_random_sample_sql(table_b, limit, ex_b.config.ds_type, where_val)
    else:
        sql_a = build_sample_sql(table_a, limit, where_val, ds_type=ex_a.config.ds_type)
        sql_b = build_sample_sql(table_b, limit, where_val, ds_type=ex_b.config.ds_type)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=limit),
        lambda: ex_b.run(sql_b, max_rows=limit),
    )

    mapping = parse_column_mapping(col_mapping_str) if col_mapping_str else {}
    if mapping:
        rb_cols = apply_column_mapping(rb.columns, mapping)
    else:
        rb_cols = rb.columns

    rows_a = list(ra.rows)
    rows_b = list(rb.rows)

    if masking_on:
        sens_a = detect_sensitive_columns(ra.columns, rows_a)
        sens_b = detect_sensitive_columns(rb_cols, rows_b)
        if sens_a:
            rows_a = mask_rows(ra.columns, rows_a, sens_a)
        if sens_b:
            rows_b = mask_rows(rb_cols, rows_b, sens_b)

    key_cols = [k.strip() for k in key_cols_str.split(",") if k.strip()] if key_cols_str else []

    fallback_notice = ""
    if key_cols:
        try:
            kd_result = diff_by_key(ra.columns, rows_a, rb_cols, rows_b, key_cols)
            return kd_result, build_keyed_diff_card(kd_result, lang_val)
        except (ValueError, IndexError) as exc:
            _log.warning("Keyed diff failed for %s / %s, falling back to "
                         "positional diff", table_a, table_b, exc_info=True)
            fallback_notice = (
                '<div style="border:1px solid #fde68a;border-radius:8px;'
                'padding:8px 12px;background:#fffbeb;margin-bottom:8px;'
                'color:#d97706;font-size:12px;">⚠️ '
                f'{dc(lang_val, "dc_keyed_diff_fallback").format(err=_esc_html(str(exc)))}'
                '</div>'
            )

    diff = diff_results(ra.columns, rows_a, rb_cols, rows_b)
    cols = ra.columns or rb_cols
    return diff, fallback_notice + build_sample_diff_card(diff, lang_val, columns=cols)


def agg_inner(
    session: SessionState, table_a: str, table_b: str, lang_val: str,
    where_val: str = "", desc_a: Any = None, desc_b: Any = None,
) -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    if desc_a is None and desc_b is None:
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(table_a),
            lambda: ex_b.describe_table(table_b),
        )
    else:
        if desc_a is None:
            desc_a = ex_a.describe_table(table_a)
        if desc_b is None:
            desc_b = ex_b.describe_table(table_b)
    names_a = {c.name.lower(): c for c in desc_a.columns}
    names_b = {c.name.lower(): c for c in desc_b.columns}
    shared_numeric = [
        c.name for key, c in names_a.items()
        if key in names_b and is_numeric_type(c.dtype)
    ]
    if not shared_numeric:
        return AggregateResult(table_a, table_b), (
            '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
            'background:#f9fafb;margin-bottom:8px;">'
            f'<b style="color:#6b7280;">{dc(lang_val, "dc_agg_result")}</b> — '
            f'{dc(lang_val, "dc_no_numeric")}</div>'
        )
    sql_a = build_aggregate_sql(table_a, shared_numeric, where_val,
                                ds_type=ex_a.config.ds_type)
    sql_b = build_aggregate_sql(table_b, shared_numeric, where_val,
                                ds_type=ex_b.config.ds_type)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=1),
        lambda: ex_b.run(sql_b, max_rows=1),
    )
    row_a = ra.rows[0] if ra.rows else ()
    row_b = rb.rows[0] if rb.rows else ()
    result = compare_aggregates(table_a, row_a, table_b, row_b, shared_numeric)
    return result, build_aggregate_card(result, lang_val)


# ── Validated user-facing actions (one per core button) ──


def _run_validated(session: SessionState, name: str, fn: Any,
                   table_a: str, table_b: str, lang_val: str) -> str:
    """Apply the legacy guard semantics (connected + tables + error card)."""
    fn.__name__ = name
    return _with_validation(session, fn)(table_a, table_b, lang_val)


def compare_schema(session: SessionState, table_a: str, table_b: str,
                   lang_val: str = "en", where_val: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = schema_inner(session, ta, tb, lv, where_val)
        store_partial(session, "schema", result)
        return html
    return _run_validated(session, "compare_schema", _fn, table_a, table_b, lang_val)


def compare_count(session: SessionState, table_a: str, table_b: str,
                  lang_val: str = "en", where_val: str = "",
                  threshold_str: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        threshold = parse_threshold(threshold_str)
        result, _ = count_inner(session, ta, tb, lv, where_val)
        html = build_count_card(result, lv, threshold)
        store_partial(session, "row_count", result)
        return html
    return _run_validated(session, "compare_count", _fn, table_a, table_b, lang_val)


def compare_sample(session: SessionState, table_a: str, table_b: str,
                   lang_val: str = "en", where_val: str = "",
                   key_cols_str: str = "", strategy: str = "TOP N",
                   col_mapping_str: str = "", masking_on: bool = True,
                   stratified_col: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = sample_inner(
            session, ta, tb, lv, where_val, key_cols_str,
            strategy, col_mapping_str, masking_on, stratified_col)
        if isinstance(result, KeyedDiffResult):
            store_partial(session, "keyed_diff", result)
        else:
            store_partial(session, "sample", result)
        return html
    return _run_validated(session, "compare_sample", _fn, table_a, table_b, lang_val)


def compare_aggregate(session: SessionState, table_a: str, table_b: str,
                      lang_val: str = "en", where_val: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = agg_inner(session, ta, tb, lv, where_val)
        store_partial(session, "aggregate", result)
        return html
    return _run_validated(session, "compare_aggregate", _fn, table_a, table_b, lang_val)
