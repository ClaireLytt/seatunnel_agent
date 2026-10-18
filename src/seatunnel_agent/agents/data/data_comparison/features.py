"""Gradio-free feature-accordion analyses + their REST endpoints.

Ticket 06: the seven analysis accordions of the Data Comparison page —
incremental watermark compare, quality rules, skew, checksum (incl.
chunked verification), partition, custom aggregates and custom SQL A/B
— extracted from the ``render_data_comparison_page`` closures in
``ui.py`` so the REST layer and the legacy Gradio page share one
implementation (the ``actions.py`` pattern). Every function takes the
per-session :class:`~.registry.SessionState` explicitly.

The module also owns the feature endpoints on its own ``APIRouter``;
``api.py`` includes it so the hub keeps mounting a single router.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter

from seatunnel_agent.agents.data.data_comparison.actions import (
    snap_executors,
    store_partial,
)
from seatunnel_agent.agents.data.data_comparison.chunked import compare_chunked
from seatunnel_agent.agents.data.data_comparison.comparator import (
    ChecksumResult,
    CustomAggResult,
    PartitionResult,
    ProfileResult,
    SkewItem,
    SkewResult,
    apply_column_mapping,
    build_checksum_sql,
    build_count_sql,
    build_custom_agg_sql,
    build_incremental_sql,
    build_partition_count_sql,
    build_profile_sql,
    build_skew_sql,
    check_quality_rules,
    compare_checksums,
    compare_custom_aggs,
    compare_partitions,
    compare_profiles,
    compare_skew,
    detect_sensitive_columns,
    diff_by_key,
    mask_rows,
    parse_column_mapping,
    parse_custom_agg_expressions,
    parse_quality_rules,
    run_parallel,
)
from seatunnel_agent.agents.data.data_comparison.deps import (
    OptionsRequest,
    get_session_or_404,
)
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import SessionState
from seatunnel_agent.agents.data.data_comparison.ui_cards import (
    build_checksum_card,
    build_chunked_card,
    build_custom_agg_card,
    build_keyed_diff_card,
    build_partition_card,
    build_profile_card,
    build_quality_card,
    build_sample_diff_card,
    build_skew_card,
    build_sql_result_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _CHECKSUM_MAX_ROWS,
    _DDL_KEYWORDS,
    _INCREMENTAL_LIMIT,
    _MAX_AGG_COLUMNS,
    _PARTITION_MAX_ROWS,
    _SKEW_MAX_COLUMNS,
    _SKEW_MAX_ROWS,
    _error_html,
    _validate_where,
    _with_validation,
)
from seatunnel_agent.agents.data.text2sql.differ import diff_results


def _run_validated(session: SessionState, name: str, fn: Any,
                   table_a: str, table_b: str, lang_val: str) -> str:
    """Apply the legacy guard semantics (connected + tables + error card)."""
    fn.__name__ = name
    return _with_validation(session, fn)(table_a, table_b, lang_val)


# ── Column profile (shared helper: quality rules evaluate a profile) ──


def profile_inner(session: SessionState, table_a: str, table_b: str,
                  lang_val: str, where_val: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    desc_a, desc_b = run_parallel(
        lambda: ex_a.describe_table(table_a),
        lambda: ex_b.describe_table(table_b),
    )
    names_a = {c.name.lower(): c.name for c in desc_a.columns}
    names_b = {c.name.lower(): c.name for c in desc_b.columns}
    shared_cols = [names_a[k] for k in names_a if k in names_b]

    if not shared_cols:
        return ProfileResult(table_a, table_b), build_profile_card(
            ProfileResult(table_a, table_b), lang_val)

    sql_a = build_profile_sql(table_a, shared_cols, where_val,
                              ds_type=ex_a.config.ds_type)
    sql_b = build_profile_sql(table_b, shared_cols, where_val,
                              ds_type=ex_b.config.ds_type)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=1),
        lambda: ex_b.run(sql_b, max_rows=1),
    )
    row_a = ra.rows[0] if ra.rows else ()
    row_b = rb.rows[0] if rb.rows else ()
    total_a = int(row_a[0]) if row_a else 0
    total_b = int(row_b[0]) if row_b else 0
    result = compare_profiles(table_a, row_a, total_a, table_b, row_b,
                              total_b, shared_cols)
    return result, build_profile_card(result, lang_val)


# ── Skew analysis ──


def skew_inner(session: SessionState, table_a: str, table_b: str,
               lang_val: str, where_val: str = "",
               skew_cols_str: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    cols = [c.strip() for c in skew_cols_str.split(",") if c.strip()]
    if not cols:
        return SkewResult(table_a, table_b), build_skew_card(
            SkewResult(table_a, table_b), lang_val)

    cols = cols[:_SKEW_MAX_COLUMNS]
    count_sql_a = build_count_sql(table_a, where_val)
    count_sql_b = build_count_sql(table_b, where_val)
    ra_cnt, rb_cnt = run_parallel(
        lambda: ex_a.run(count_sql_a, max_rows=1),
        lambda: ex_b.run(count_sql_b, max_rows=1),
    )
    total_a = int(ra_cnt.rows[0][0]) if ra_cnt.rows else 0
    total_b = int(rb_cnt.rows[0][0]) if rb_cnt.rows else 0

    def _process_skew_col(col: str) -> SkewItem:
        sql_a = build_skew_sql(table_a, col, where_val, ds_type=ex_a.config.ds_type)
        sql_b = build_skew_sql(table_b, col, where_val, ds_type=ex_b.config.ds_type)
        # sql_a/sql_b are per-call locals here, so plain capture is safe
        ra, rb = run_parallel(
            lambda: ex_a.run(sql_a, max_rows=_SKEW_MAX_ROWS),
            lambda: ex_b.run(sql_b, max_rows=_SKEW_MAX_ROWS),
        )
        return compare_skew(
            table_a, table_b, col,
            ra.rows, total_a,
            rb.rows, total_b,
        )

    with ThreadPoolExecutor(max_workers=min(len(cols), 5)) as col_pool:
        futures = [col_pool.submit(_process_skew_col, c) for c in cols]
        items: list[SkewItem] = [f.result() for f in futures]

    result = SkewResult(
        table_a=table_a, table_b=table_b,
        total_a=total_a, total_b=total_b,
        items=items,
    )
    return result, build_skew_card(result, lang_val, conn_b=ex_b.config)


def compare_skew_action(session: SessionState, table_a: str, table_b: str,
                        lang_val: str = "en", where_val: str = "",
                        skew_cols_str: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        if not skew_cols_str or not skew_cols_str.strip():
            return f'<div style="color:#dc2626;">{dc(lv, "dc_skew_no_columns")}</div>'
        result, html = skew_inner(session, ta, tb, lv, where_val, skew_cols_str)
        store_partial(session, "skew", result)
        return html
    return _run_validated(session, "compare_skew", _fn, table_a, table_b, lang_val)


# ── Checksum comparison ──


def checksum_inner(session: SessionState, table_a: str, table_b: str,
                   lang_val: str, where_val: str = "",
                   checksum_cols_str: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    cols = [c.strip() for c in checksum_cols_str.split(",") if c.strip()]
    if not cols:
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(table_a),
            lambda: ex_b.describe_table(table_b),
        )
        names_b = {c.name.lower() for c in desc_b.columns}
        cols = [c.name for c in desc_a.columns
                if c.name.lower() in names_b][:_MAX_AGG_COLUMNS]
    if not cols:
        return ChecksumResult(table_a, table_b), build_checksum_card(
            ChecksumResult(table_a, table_b), lang_val)
    sql_a = build_checksum_sql(table_a, cols, ex_a.config.ds_type, where_val)
    sql_b = build_checksum_sql(table_b, cols, ex_b.config.ds_type, where_val)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=_CHECKSUM_MAX_ROWS),
        lambda: ex_b.run(sql_b, max_rows=_CHECKSUM_MAX_ROWS),
    )
    result = compare_checksums(table_a, table_b, ra.rows, rb.rows)
    return result, build_checksum_card(result, lang_val)


def compare_checksum_action(session: SessionState, table_a: str, table_b: str,
                            lang_val: str = "en", where_val: str = "",
                            checksum_cols_str: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = checksum_inner(session, ta, tb, lv, where_val,
                                      checksum_cols_str)
        store_partial(session, "checksum", result)
        return html
    return _run_validated(session, "compare_checksum", _fn,
                          table_a, table_b, lang_val)


# ── Chunked (blocked) verification for large tables ──


def chunked_inner(session: SessionState, table_a: str, table_b: str,
                  lang_val: str, where_val: str = "", key_cols_str: str = "",
                  checksum_cols_str: str = "",
                  col_mapping_str: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    key_cols = [k.strip() for k in (key_cols_str or "").split(",") if k.strip()]
    if not key_cols:
        return None, (
            '<div style="padding:10px;color:#d97706;background:#fffbeb;'
            'border-radius:8px;margin-bottom:8px;">'
            f'{dc(lang_val, "dc_chunked_need_pk")}</div>')
    pk = key_cols[0]
    mapping = parse_column_mapping(col_mapping_str) if col_mapping_str else {}
    cols = [c.strip() for c in (checksum_cols_str or "").split(",") if c.strip()]
    if not cols:
        desc_a, desc_b = run_parallel(
            lambda: ex_a.describe_table(table_a),
            lambda: ex_b.describe_table(table_b),
        )
        names_a = {c.name.lower(): c.name for c in desc_a.columns}
        names_b = {c.name.lower() for c in desc_b.columns}
        cols = [names_a[k] for k in names_a
                if k != pk.lower()
                and mapping.get(names_a[k], names_a[k]).lower() in names_b]
    cols_b = [mapping.get(c, c) for c in cols]
    pk_b = mapping.get(pk, pk)
    if not cols:
        # no shared non-pk columns: hash the pk itself on each side
        cols, cols_b = [pk], [pk_b]

    def _run_a(sql: str, n: int) -> Any:
        return ex_a.run(sql, max_rows=n).rows

    def _run_b(sql: str, n: int) -> Any:
        return ex_b.run(sql, max_rows=n).rows

    result = compare_chunked(
        _run_a, _run_b, table_a, table_b, pk, cols,
        ex_a.config.ds_type, ex_b.config.ds_type, where=where_val or "",
        columns_b=cols_b, pk_column_b=pk_b)
    return result, build_chunked_card(result, lang_val)


def compare_chunked_action(session: SessionState, table_a: str, table_b: str,
                           lang_val: str = "en", where_val: str = "",
                           key_cols_str: str = "", checksum_cols_str: str = "",
                           col_mapping_str: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        result, html = chunked_inner(session, ta, tb, lv, where_val,
                                     key_cols_str, checksum_cols_str,
                                     col_mapping_str)
        if result is not None:
            store_partial(session, "chunked", result)
        return html
    return _run_validated(session, "compare_chunked", _fn,
                          table_a, table_b, lang_val)


# ── Partition comparison ──


def partition_inner(session: SessionState, table_a: str, table_b: str,
                    lang_val: str, where_val: str = "",
                    partition_col: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    if not partition_col.strip():
        return PartitionResult(table_a, table_b), build_partition_card(
            PartitionResult(table_a, table_b), lang_val)
    sql_a = build_partition_count_sql(table_a, partition_col.strip(), where_val,
                                      ds_type=ex_a.config.ds_type)
    sql_b = build_partition_count_sql(table_b, partition_col.strip(), where_val,
                                      ds_type=ex_b.config.ds_type)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=_PARTITION_MAX_ROWS),
        lambda: ex_b.run(sql_b, max_rows=_PARTITION_MAX_ROWS),
    )
    result = compare_partitions(table_a, table_b, partition_col.strip(),
                                ra.rows, rb.rows)
    return result, build_partition_card(result, lang_val)


def compare_partition_action(session: SessionState, table_a: str, table_b: str,
                             lang_val: str = "en", where_val: str = "",
                             partition_col: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        if not partition_col or not partition_col.strip():
            return f'<div style="color:#dc2626;">{dc(lv, "dc_partition_col_hint")}</div>'
        result, html = partition_inner(session, ta, tb, lv, where_val,
                                       partition_col)
        store_partial(session, "partition", result)
        return html
    return _run_validated(session, "compare_partition", _fn,
                          table_a, table_b, lang_val)


# ── Custom aggregates ──


def custom_agg_inner(session: SessionState, table_a: str, table_b: str,
                     lang_val: str, where_val: str = "",
                     expressions_str: str = "") -> tuple[Any, str]:
    ex_a, ex_b = snap_executors(session)
    expressions = parse_custom_agg_expressions(expressions_str)
    if not expressions:
        return CustomAggResult(table_a, table_b), build_custom_agg_card(
            CustomAggResult(table_a, table_b), lang_val)
    sql_a = build_custom_agg_sql(table_a, expressions, where_val)
    sql_b = build_custom_agg_sql(table_b, expressions, where_val)
    ra, rb = run_parallel(
        lambda: ex_a.run(sql_a, max_rows=1),
        lambda: ex_b.run(sql_b, max_rows=1),
    )
    row_a = ra.rows[0] if ra.rows else ()
    row_b = rb.rows[0] if rb.rows else ()
    result = compare_custom_aggs(table_a, row_a, table_b, row_b, expressions)
    return result, build_custom_agg_card(result, lang_val)


def compare_custom_agg_action(session: SessionState, table_a: str,
                              table_b: str, lang_val: str = "en",
                              where_val: str = "",
                              expressions_str: str = "") -> str:
    def _fn(ta: str, tb: str, lv: str) -> str:
        ok, msg = _validate_where(where_val, lv)
        if not ok:
            return msg
        if not expressions_str or not expressions_str.strip():
            return f'<div style="color:#dc2626;">{dc(lv, "dc_custom_agg_hint")}</div>'
        result, html = custom_agg_inner(session, ta, tb, lv, where_val,
                                        expressions_str)
        store_partial(session, "custom_agg", result)
        return html
    return _run_validated(session, "compare_custom_agg", _fn,
                          table_a, table_b, lang_val)


# ── Custom SQL A/B comparison ──


def compare_sql_action(session: SessionState, sql_a_text: str,
                       sql_b_text: str, lang_val: str = "en") -> str:
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
    if not sql_a_text.strip() or not sql_b_text.strip():
        return dc(lang_val, "dc_sql_readonly_only")

    for sql_text in (sql_a_text, sql_b_text):
        stripped = sql_text.strip().upper()
        if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
            return dc(lang_val, "dc_sql_readonly_only")
        if _DDL_KEYWORDS.search(sql_text):
            return dc(lang_val, "dc_sql_readonly_only")

    try:
        ex_a, ex_b = snap_executors(session)
        ra, rb = run_parallel(
            lambda: ex_a.run(sql_a_text.strip(), max_rows=200),
            lambda: ex_b.run(sql_b_text.strip(), max_rows=200),
        )
        diff = diff_results(ra.columns, ra.rows, rb.columns, rb.rows)
        cols = ra.columns or rb.columns
        return build_sql_result_card(diff, lang_val, columns=cols)
    except Exception as e:
        return _error_html(lang_val, e)


# ── Incremental (watermark) comparison ──


def compare_incremental_action(session: SessionState, table_a: str,
                               table_b: str, lang_val: str = "en",
                               where_val: str = "", watermark_col: str = "",
                               watermark_val: str = "", key_cols_str: str = "",
                               col_mapping_str: str = "",
                               masking_on: bool = True) -> str:
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
    if not table_a or not table_b:
        return dc(lang_val, "dc_select_tables")
    if not watermark_col.strip():
        return dc(lang_val, "dc_watermark_hint")
    ok, msg = _validate_where(where_val, lang_val)
    if not ok:
        return msg
    try:
        ex_a, ex_b = snap_executors(session)
        last_val = watermark_val.strip()
        sql_a = build_incremental_sql(table_a, watermark_col.strip(), last_val,
                                      _INCREMENTAL_LIMIT, where_val,
                                      ds_type=ex_a.config.ds_type)
        sql_b = build_incremental_sql(table_b, watermark_col.strip(), last_val,
                                      _INCREMENTAL_LIMIT, where_val,
                                      ds_type=ex_b.config.ds_type)
        ra, rb = run_parallel(
            lambda: ex_a.run(sql_a, max_rows=_INCREMENTAL_LIMIT),
            lambda: ex_b.run(sql_b, max_rows=_INCREMENTAL_LIMIT),
        )
        mapping = parse_column_mapping(col_mapping_str) if col_mapping_str else {}
        rb_cols = apply_column_mapping(rb.columns, mapping) if mapping else rb.columns
        rows_a, rows_b = list(ra.rows), list(rb.rows)
        if masking_on:
            sa = detect_sensitive_columns(ra.columns, rows_a)
            sb = detect_sensitive_columns(rb_cols, rows_b)
            if sa:
                rows_a = mask_rows(ra.columns, rows_a, sa)
            if sb:
                rows_b = mask_rows(rb_cols, rows_b, sb)
        key_cols = ([k.strip() for k in key_cols_str.split(",") if k.strip()]
                    if key_cols_str else [])
        if key_cols:
            kd_result = diff_by_key(ra.columns, rows_a, rb_cols, rows_b, key_cols)
            store_partial(session, "keyed_diff", kd_result)
            return build_keyed_diff_card(kd_result, lang_val)
        diff = diff_results(ra.columns, rows_a, rb_cols, rows_b)
        store_partial(session, "sample", diff)
        return build_sample_diff_card(diff, lang_val, columns=ra.columns or rb_cols)
    except Exception as e:
        return _error_html(lang_val, e)


# ── Quality rules check ──


def check_quality_action(session: SessionState, table_a: str, table_b: str,
                         lang_val: str = "en", where_val: str = "",
                         quality_rules_str: str = "") -> str:
    with session.lock:
        if session.executor_a is None or session.executor_b is None:
            return dc(lang_val, "dc_connect_both")
    if not table_a or not table_b:
        return dc(lang_val, "dc_select_tables")
    if not quality_rules_str.strip():
        return dc(lang_val, "dc_quality_rules_hint")
    try:
        rules = parse_quality_rules(quality_rules_str)
        if not rules:
            return dc(lang_val, "dc_quality_rules_hint")
        profile_result, _ = profile_inner(session, table_a, table_b,
                                          lang_val, where_val)
        results_a = check_quality_rules(rules, profile_result, side="a")
        results_b = check_quality_rules(rules, profile_result, side="b")
        return (build_quality_card(results_a, lang_val, side_label="A")
                + build_quality_card(results_b, lang_val, side_label="B"))
    except Exception as e:
        return _error_html(lang_val, e)


# ── REST endpoints (included into api.py's router) ──────────────────

router = APIRouter()


class FeatureRequest(OptionsRequest):
    """Feature-accordion action request: shared options + per-feature fields."""

    # incremental
    watermark_col: str = ""
    watermark_val: str = ""
    # quality
    quality_rules: str = ""
    # skew
    skew_columns: str = ""
    # checksum / chunked
    checksum_columns: str = ""
    # partition
    partition_col: str = ""
    # custom aggregates
    expressions: str = ""
    # custom SQL A/B
    sql_a: str = ""
    sql_b: str = ""


def _session_of(req: FeatureRequest) -> SessionState:
    return get_session_or_404(req.session_id)


@router.post("/compare/incremental")
def compare_incremental(req: FeatureRequest) -> dict[str, str]:
    """Incremental watermark comparison card (keyed or positional diff)."""
    return {"html": compare_incremental_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.watermark_col, req.watermark_val, req.key_columns,
        req.column_mapping, req.masking)}


@router.post("/compare/quality")
def compare_quality(req: FeatureRequest) -> dict[str, str]:
    """Quality-rule check cards for both sides."""
    return {"html": check_quality_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.quality_rules)}


@router.post("/compare/skew")
def compare_skew_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Data-skew analysis card over the requested columns."""
    return {"html": compare_skew_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.skew_columns)}


@router.post("/compare/checksum")
def compare_checksum_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Per-segment checksum comparison card."""
    return {"html": compare_checksum_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.checksum_columns)}


@router.post("/compare/chunked")
def compare_chunked_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Chunked (blocked) verification card; key_columns[0] is the PK."""
    return {"html": compare_chunked_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.key_columns, req.checksum_columns, req.column_mapping)}


@router.post("/compare/partition")
def compare_partition_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Partition row-count comparison card."""
    return {"html": compare_partition_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.partition_col)}


@router.post("/compare/custom-agg")
def compare_custom_agg_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Custom aggregate expression comparison card."""
    return {"html": compare_custom_agg_action(
        _session_of(req), req.table_a, req.table_b, req.lang, req.where,
        req.expressions)}


@router.post("/compare/sql")
def compare_sql_endpoint(req: FeatureRequest) -> dict[str, str]:
    """Custom SQL A/B comparison card (SELECT/WITH-only, DDL guarded)."""
    return {"html": compare_sql_action(
        _session_of(req), req.sql_a, req.sql_b, req.lang)}


__all__ = [
    "router",
    "profile_inner",
    "skew_inner",
    "compare_skew_action",
    "checksum_inner",
    "compare_checksum_action",
    "chunked_inner",
    "compare_chunked_action",
    "partition_inner",
    "compare_partition_action",
    "custom_agg_inner",
    "compare_custom_agg_action",
    "compare_sql_action",
    "compare_incremental_action",
    "check_quality_action",
]
