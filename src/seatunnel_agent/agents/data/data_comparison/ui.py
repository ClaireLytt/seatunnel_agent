"""Gradio page for the Data Comparison agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Data Comparison", "/datacompare")``.  No LLM — pure
deterministic comparison of two data sources.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gradio as gr

from seatunnel_agent.agents.data.data_comparison.comparator import (
    AggregateResult,
    BatchFullItem,
    ChecksumResult,
    CompareReport,
    CustomAggResult,
    KeyedDiffResult,
    PartitionResult,
    ProfileResult,
    RowCountResult,
    SkewItem,
    SkewResult,
    apply_column_mapping,
    build_aggregate_sql,
    build_checksum_sql,
    build_count_sql,
    build_custom_agg_sql,
    build_incremental_sql,
    build_partition_count_sql,
    build_profile_sql,
    build_random_sample_sql,
    build_row_count_result,
    build_sample_sql,
    build_skew_sql,
    build_stratified_sample_sql,
    build_trend_data,
    check_quality_rules,
    check_trend_alerts,
    compare_aggregates,
    compare_checksums,
    compare_custom_aggs,
    compare_partitions,
    compare_profiles,
    compare_schemas,
    compare_skew,
    detect_sensitive_columns,
    diff_by_key,
    diff_reports,
    find_common_tables,
    generate_diff_sql,
    generate_sync_config,
    get_upstream_tables,
    is_numeric_type,
    mask_rows,
    parse_alert_rules,
    parse_column_mapping,
    parse_custom_agg_expressions,
    parse_quality_rules,
    parse_threshold,
    run_parallel,
)
from seatunnel_agent.agents.data.data_comparison.connect import connect_side
from seatunnel_agent.agents.data.data_comparison.i18n import dc
from seatunnel_agent.agents.data.data_comparison.registry import get_registry
from seatunnel_agent.agents.data.data_comparison.ui_cards import (  # noqa: F401
    _threshold_badge,
    build_aggregate_card,
    build_batch_count_card,
    build_batch_full_card,
    build_batch_template_card,
    build_checksum_card,
    build_chunked_card,
    build_count_card,
    build_custom_agg_card,
    build_diff_sql_card,
    build_keyed_diff_card,
    build_lineage_card,
    build_partition_card,
    build_profile_card,
    build_quality_card,
    build_report_diff_card,
    build_sample_diff_card,
    build_schema_diff_card,
    build_skew_card,
    build_sql_result_card,
    build_standalone_report,
    build_summary_card,
    build_trend_alert_card,
)
from seatunnel_agent.agents.data.data_comparison.ui_reports import (  # noqa: F401
    _download_dir,
    _export_report_csv,
    _export_report_excel,
)

# Module-level helpers moved to data_comparison.ui_shared / ui_cards / ui_reports.
# Re-exported here because tests and other modules import them from this path.
from seatunnel_agent.agents.data.data_comparison.ui_shared import (  # noqa: F401
    _CHECKSUM_MAX_ROWS,
    _DDL_KEYWORDS,
    _DEFAULT_LANG,
    _DEFAULT_SCHEDULE_MIN,
    _DELTA_WARN_PCT,
    _DS_CHOICES,
    _DS_LABEL_TO_KEY,
    _ERR_ESSENCE_RES,
    _INCREMENTAL_LIMIT,
    _LIST_LIMIT,
    _MAX_AGG_COLUMNS,
    _MAX_REPORT_FILES,
    _NEEDS_AUTH,
    _NEEDS_HOST,
    _PARTITION_MAX_ROWS,
    _PRESETS_STORE,
    _REPORTS_DIR,
    _SAMPLE_LIMIT,
    _SAMPLE_STRATEGIES,
    _SKEW_MAX_COLUMNS,
    _SKEW_MAX_ROWS,
    _STRATIFIED_PER_GROUP,
    _SUMMARY_MAX_ITEMS,
    _TD,
    _TEMPLATES_STORE,
    _TH,
    _WEBHOOK_TIMEOUT,
    _build_webhook_summary,
    _details_card,
    _error_html,
    _esc_html,
    _get_matplotlib,
    _log,
    _send_webhook,
    _validate_where,
    _with_validation,
)
from seatunnel_agent.agents.data.text2sql.differ import diff_results
from seatunnel_agent.agents.data.text2sql.executor import (
    DIALECT_NAMES,
    DS_DEFAULTS,
    DatabaseConfig,
    config_from_env,
    create_executor,
)

# ---------------------------------------------------------------------------
# Page renderer
# ---------------------------------------------------------------------------

def render_data_comparison_page(app=None) -> None:
    """Render the Data Comparison page components."""
    from dotenv import load_dotenv
    load_dotenv()

    lang = _DEFAULT_LANG
    t = lambda k: dc(lang, k)

    # One registry session per page render. The hub renders this page once
    # per process, so this preserves the previous process-global semantics of
    # the module-closure state dict while keying state through the registry.
    session = get_registry().create()

    # ── Connection helper (shared by A / B) ──
    # Core logic lives in connect.connect_side (Gradio-free, shared with the
    # REST layer in api.py); this wrapper maps the dialect label to the
    # datasource key and the result to Gradio updates.
    def _do_connect(ds_label, host, port, db, username, password, lang_val, side):
        def _err(msg):
            return msg, gr.update(), gr.update(), gr.update(), gr.update()

        ds_type = _DS_LABEL_TO_KEY.get(ds_label)
        if ds_type is None:
            return _err(f"❌ {dc(lang_val, 'dc_error')}: "
                        f"unknown datasource {_esc_html(str(ds_label))}")
        # Hidden Gradio textboxes (auth/host fields for engines that don't
        # need them) submit None from the browser, not "" — connect_side strips.
        result = connect_side(session, side, ds_type,
                              host, port, db, username, password, lang_val)
        if not result.ok:
            return _err(result.error)
        cfg = result.resolved
        # Backfill connection fields so env/default fallbacks are visible
        if ds_type == "sqlite":
            host_upd, port_upd = gr.update(), gr.update()
        else:
            host_upd, port_upd = gr.update(value=cfg.host), gr.update(value=str(cfg.port))
        return (result.status, gr.update(choices=result.tables, value=None),
                host_upd, port_upd, gr.update(value=cfg.database))

    # ── Inner comparison logic (no validation — used by both single + all) ──

    def _snap_executors():
        with session.lock:
            return session.executor_a, session.executor_b

    def _schema_inner(table_a, table_b, lang_val, where_val="", desc_a=None, desc_b=None):
        ex_a, ex_b = _snap_executors()
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

    def _count_inner(table_a, table_b, lang_val, where_val=""):
        ex_a, ex_b = _snap_executors()
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

    def _sample_inner(table_a, table_b, lang_val, where_val="", key_cols_str="",
                      strategy="TOP N", col_mapping_str="", masking_on=True,
                      stratified_col=""):
        ex_a, ex_b = _snap_executors()
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

    def _agg_inner(table_a, table_b, lang_val, where_val="", desc_a=None, desc_b=None):
        ex_a, ex_b = _snap_executors()
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

    def _profile_inner(table_a, table_b, lang_val, where_val=""):
        ex_a, ex_b = _snap_executors()
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
        result = compare_profiles(table_a, row_a, total_a, table_b, row_b, total_b, shared_cols)
        return result, build_profile_card(result, lang_val)

    # ── Wrapped callbacks ──

    def _store_partial(key: str, value: Any) -> None:
        """Store a single comparison result into the report."""
        with session.lock:
            if session.last_report is None:
                session.last_report = CompareReport()
            setattr(session.last_report, key, value)

    def _compare_schema_fn(table_a, table_b, lang_val, where_val):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _schema_inner(table_a, table_b, lang_val, where_val)
        _store_partial("schema", result)
        return html

    def _compare_count_fn(table_a, table_b, lang_val, where_val, threshold_str=""):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        threshold = parse_threshold(threshold_str)
        result, html = _count_inner(table_a, table_b, lang_val, where_val)
        html = build_count_card(result, lang_val, threshold)
        _store_partial("row_count", result)
        return html

    def _compare_sample_fn(table_a, table_b, lang_val, where_val, key_cols_str,
                           strategy="TOP N", col_mapping_str="", masking_on=True,
                           stratified_col=""):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _sample_inner(
            table_a, table_b, lang_val, where_val, key_cols_str,
            strategy, col_mapping_str, masking_on, stratified_col)
        if isinstance(result, KeyedDiffResult):
            _store_partial("keyed_diff", result)
        else:
            _store_partial("sample", result)
        return html

    def _compare_agg_fn(table_a, table_b, lang_val, where_val):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _agg_inner(table_a, table_b, lang_val, where_val)
        _store_partial("aggregate", result)
        return html

    def _compare_profile_fn(table_a, table_b, lang_val, where_val):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _profile_inner(table_a, table_b, lang_val, where_val)
        _store_partial("profile", result)
        return html

    # ── Skew analysis (BB) ──

    def _skew_inner(table_a, table_b, lang_val, where_val="", skew_cols_str=""):
        ex_a, ex_b = _snap_executors()
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

        from concurrent.futures import ThreadPoolExecutor as _LocalPool

        def _process_skew_col(col):
            sql_a = build_skew_sql(table_a, col, where_val, ds_type=ex_a.config.ds_type)
            sql_b = build_skew_sql(table_b, col, where_val, ds_type=ex_b.config.ds_type)
            ra, rb = run_parallel(
                lambda s=sql_a: ex_a.run(s, max_rows=_SKEW_MAX_ROWS),
                lambda s=sql_b: ex_b.run(s, max_rows=_SKEW_MAX_ROWS),
            )
            return compare_skew(
                table_a, table_b, col,
                ra.rows, total_a,
                rb.rows, total_b,
            )

        with _LocalPool(max_workers=min(len(cols), 5)) as col_pool:
            futures = [col_pool.submit(_process_skew_col, c) for c in cols]
            items: list[SkewItem] = [f.result() for f in futures]

        result = SkewResult(
            table_a=table_a, table_b=table_b,
            total_a=total_a, total_b=total_b,
            items=items,
        )
        return result, build_skew_card(result, lang_val,
                                       conn_b=ex_b.config)

    def _compare_skew_fn(table_a, table_b, lang_val, where_val, skew_cols_str):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        if not skew_cols_str or not skew_cols_str.strip():
            return f'<div style="color:#dc2626;">{dc(lang_val, "dc_skew_no_columns")}</div>'
        result, html = _skew_inner(table_a, table_b, lang_val, where_val, skew_cols_str)
        _store_partial("skew", result)
        return html

    _compare_schema = _with_validation(session, _compare_schema_fn)
    _compare_count = _with_validation(session, _compare_count_fn)
    _compare_sample = _with_validation(session, _compare_sample_fn)
    _compare_agg = _with_validation(session, _compare_agg_fn)
    _compare_profile = _with_validation(session, _compare_profile_fn)
    _compare_skew = _with_validation(session, _compare_skew_fn)

    # ── Checksum comparison (CC) ──

    def _checksum_inner(table_a, table_b, lang_val, where_val="", checksum_cols_str=""):
        ex_a, ex_b = _snap_executors()
        cols = [c.strip() for c in checksum_cols_str.split(",") if c.strip()]
        if not cols:
            desc_a, desc_b = run_parallel(
                lambda: ex_a.describe_table(table_a),
                lambda: ex_b.describe_table(table_b),
            )
            names_b = {c.name.lower() for c in desc_b.columns}
            cols = [c.name for c in desc_a.columns if c.name.lower() in names_b][:_MAX_AGG_COLUMNS]
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

    def _compare_checksum_fn(table_a, table_b, lang_val, where_val, checksum_cols_str=""):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _checksum_inner(table_a, table_b, lang_val, where_val, checksum_cols_str)
        _store_partial("checksum", result)
        return html

    _compare_checksum = _with_validation(session, _compare_checksum_fn)

    # ── Chunked (blocked) verification for large tables ──

    def _chunked_inner(table_a, table_b, lang_val, where_val="",
                       key_cols_str="", checksum_cols_str="",
                       col_mapping_str=""):
        from seatunnel_agent.agents.data.data_comparison.chunked import compare_chunked
        ex_a, ex_b = _snap_executors()
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

        def _run_a(sql, n):
            return ex_a.run(sql, max_rows=n).rows

        def _run_b(sql, n):
            return ex_b.run(sql, max_rows=n).rows

        result = compare_chunked(
            _run_a, _run_b, table_a, table_b, pk, cols,
            ex_a.config.ds_type, ex_b.config.ds_type, where=where_val or "",
            columns_b=cols_b, pk_column_b=pk_b)
        return result, build_chunked_card(result, lang_val)

    def _compare_chunked_fn(table_a, table_b, lang_val, where_val,
                            key_cols_str="", checksum_cols_str="",
                            col_mapping_str=""):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        result, html = _chunked_inner(table_a, table_b, lang_val, where_val,
                                      key_cols_str, checksum_cols_str,
                                      col_mapping_str)
        if result is not None:
            _store_partial("chunked", result)
        return html

    _compare_chunked_btn_fn = _with_validation(session, _compare_chunked_fn)

    # ── Partition comparison (DD) ──

    def _partition_inner(table_a, table_b, lang_val, where_val="", partition_col=""):
        ex_a, ex_b = _snap_executors()
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

    def _compare_partition_fn(table_a, table_b, lang_val, where_val, partition_col):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        if not partition_col or not partition_col.strip():
            return f'<div style="color:#dc2626;">{dc(lang_val, "dc_partition_col_hint")}</div>'
        result, html = _partition_inner(table_a, table_b, lang_val, where_val, partition_col)
        _store_partial("partition", result)
        return html

    _compare_partition = _with_validation(session, _compare_partition_fn)

    # ── Custom aggregates (EE) ──

    def _custom_agg_inner(table_a, table_b, lang_val, where_val="", expressions_str=""):
        ex_a, ex_b = _snap_executors()
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

    def _compare_custom_agg_fn(table_a, table_b, lang_val, where_val, expressions_str):
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        if not expressions_str or not expressions_str.strip():
            return f'<div style="color:#dc2626;">{dc(lang_val, "dc_custom_agg_hint")}</div>'
        result, html = _custom_agg_inner(table_a, table_b, lang_val, where_val, expressions_str)
        _store_partial("custom_agg", result)
        return html

    _compare_custom_agg = _with_validation(session, _compare_custom_agg_fn)

    # ── Custom SQL comparison (B) ──

    def _compare_sql(sql_a_text, sql_b_text, lang_val):
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
            with session.lock:
                ex_a, ex_b = session.executor_a, session.executor_b
            ra, rb = run_parallel(
                lambda: ex_a.run(sql_a_text.strip(), max_rows=200),
                lambda: ex_b.run(sql_b_text.strip(), max_rows=200),
            )
            diff = diff_results(ra.columns, ra.rows, rb.columns, rb.rows)
            cols = ra.columns or rb.columns
            return build_sql_result_card(diff, lang_val, columns=cols)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Compare All (F — structured report, G — schema cache, H — progress) ──

    def _compare_all(table_a, table_b, lang_val, where_val, key_cols_str,
                     threshold_str="", strategy="TOP N", col_mapping_str="",
                     masking_on=True, webhook_url="", notify_on_fail=False,
                     skew_cols_str="", stratified_col="",
                     checksum_cols_str="", partition_col="", custom_agg_str="",
                     progress=gr.Progress()):
        _log.info("compare_all start: tables=%r/%r lang=%r", table_a, table_b, lang_val)
        with session.lock:
            if session.executor_a is None or session.executor_b is None:
                _log.info("compare_all early-return: executors not connected")
                return dc(lang_val, "dc_connect_both")
        if not table_a or not table_b:
            _log.info("compare_all early-return: tables not selected")
            return dc(lang_val, "dc_select_tables")
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg

        threshold = parse_threshold(threshold_str)

        def _safe_progress(val, desc=""):
            try:
                progress(val, desc=desc)
            except Exception:
                pass

        try:
            t0 = time.perf_counter()
            stage_ms: list[tuple[str, int]] = []
            _stage_t = t0

            def _mark(name: str) -> None:
                nonlocal _stage_t
                now = time.perf_counter()
                stage_ms.append((name, int((now - _stage_t) * 1000)))
                _stage_t = now

            ex_a, ex_b = _snap_executors()

            _safe_progress(0.1, dc(lang_val, "dc_running"))
            desc_a, desc_b = run_parallel(
                lambda: ex_a.describe_table(table_a),
                lambda: ex_b.describe_table(table_b),
            )

            _mark("describe")
            _safe_progress(0.25, dc(lang_val, "dc_running"))
            schema_result, schema_html = _schema_inner(table_a, table_b, lang_val, where_val, desc_a, desc_b)

            _mark("schema")
            _safe_progress(0.4, dc(lang_val, "dc_running"))
            count_result, _ = _count_inner(table_a, table_b, lang_val, where_val)
            count_html = build_count_card(count_result, lang_val, threshold)

            _mark("count")
            _safe_progress(0.55, dc(lang_val, "dc_running"))
            sample_result, sample_html = _sample_inner(
                table_a, table_b, lang_val, where_val, key_cols_str,
                strategy, col_mapping_str, masking_on, stratified_col)

            _mark("sample")
            _safe_progress(0.7, dc(lang_val, "dc_running"))
            agg_result, agg_html = _agg_inner(table_a, table_b, lang_val, where_val, desc_a, desc_b)

            _mark("aggregate")
            _safe_progress(0.8, dc(lang_val, "dc_running"))
            profile_result, profile_html = _profile_inner(table_a, table_b, lang_val, where_val)

            _mark("profile")
            skew_result = None
            skew_html = ""
            if skew_cols_str and skew_cols_str.strip():
                _safe_progress(0.84, dc(lang_val, "dc_running"))
                skew_result, skew_html = _skew_inner(
                    table_a, table_b, lang_val, where_val, skew_cols_str)

            checksum_result = None
            checksum_html = ""
            if checksum_cols_str and checksum_cols_str.strip():
                _safe_progress(0.88, dc(lang_val, "dc_running"))
                checksum_result, checksum_html = _checksum_inner(
                    table_a, table_b, lang_val, where_val, checksum_cols_str)

            partition_result = None
            partition_html = ""
            if partition_col and partition_col.strip():
                _safe_progress(0.92, dc(lang_val, "dc_running"))
                partition_result, partition_html = _partition_inner(
                    table_a, table_b, lang_val, where_val, partition_col)

            custom_agg_result = None
            custom_agg_html = ""
            if custom_agg_str and custom_agg_str.strip():
                _safe_progress(0.96, dc(lang_val, "dc_running"))
                custom_agg_result, custom_agg_html = _custom_agg_inner(
                    table_a, table_b, lang_val, where_val, custom_agg_str)

            elapsed = int((time.perf_counter() - t0) * 1000)

            keyed_diff = sample_result if isinstance(sample_result, KeyedDiffResult) else None
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

            has_diffs = (
                (schema_result and schema_result.has_changes)
                or (count_result and count_result.delta != 0)
                or (agg_result and agg_result.mismatches > 0)
                or (checksum_result and checksum_result.mismatch_count > 0)
                or (partition_result and partition_result.total_delta != 0)
                or (custom_agg_result and custom_agg_result.mismatches > 0)
            )

            if webhook_url and webhook_url.strip():
                should_send = True
                if notify_on_fail and not has_diffs:
                    should_send = False
                if should_send:
                    payload = {
                        "table_a": table_a, "table_b": table_b,
                        "has_diffs": has_diffs,
                        "elapsed_ms": elapsed,
                        "row_count_delta": count_result.delta if count_result else 0,
                        "schema_changes": len(schema_result.items) if schema_result and schema_result.has_changes else 0,
                        "aggregate_mismatches": agg_result.mismatches if agg_result else 0,
                        "checksum_mismatches": checksum_result.mismatch_count if checksum_result else 0,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "summary": {
                            "count_a": count_result.count_a if count_result else 0,
                            "count_b": count_result.count_b if count_result else 0,
                            "delta_pct": count_result.delta_pct if count_result else 0,
                        },
                        "report_summary": _build_webhook_summary(report),
                    }
                    threading.Thread(
                        target=_send_webhook,
                        args=(webhook_url.strip(), payload),
                        daemon=True,
                    ).start()

            _safe_progress(1.0, "Done")
            summary_html = build_summary_card(report, lang_val)
            html = (summary_html + schema_html + count_html + sample_html
                    + agg_html + profile_html + skew_html
                    + checksum_html + partition_html + custom_agg_html)
            _log.info("compare_all done: tables=%r/%r elapsed=%dms html=%d chars stages=%s",
                      table_a, table_b, elapsed, len(html),
                      " ".join(f"{n}={ms}ms" for n, ms in stage_ms))
            return html

        except Exception as e:
            _log.exception("compare_all failed: tables=%r/%r", table_a, table_b)
            if webhook_url and webhook_url.strip():
                threading.Thread(
                    target=_send_webhook,
                    args=(webhook_url.strip(), {"error": str(e), "table_a": table_a, "table_b": table_b}),
                    daemon=True,
                ).start()
            return _error_html(lang_val, e)

    # ── Batch count (H — progress) ──

    def _batch_count(lang_val, where_val, progress=gr.Progress()):
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
                return (
                    '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
                    'background:#f9fafb;margin-bottom:8px;">'
                    f'<b style="color:#6b7280;">{dc(lang_val, "dc_batch_result")}</b> — '
                    f'{dc(lang_val, "dc_no_common")}</div>'
                )

            results: list[RowCountResult] = []
            total = len(pairs)
            for idx, (ta, tb) in enumerate(pairs):
                progress((idx + 1) / total, desc=dc(lang_val, "dc_comparing_table").format(name=ta))
                sql_a = build_count_sql(ta, where_val)
                sql_b = build_count_sql(tb, where_val)
                ra, rb = run_parallel(
                    lambda: ex_a.run(sql_a, max_rows=1),
                    lambda: ex_b.run(sql_b, max_rows=1),
                )
                ca = int(ra.rows[0][0]) if ra.rows else 0
                cb = int(rb.rows[0][0]) if rb.rows else 0
                results.append(build_row_count_result(ta, ca, tb, cb))

            _store_partial("batch_counts", results)

            return build_batch_count_card(results, lang_val)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Report persistence (E) ──

    def _save_report(table_a, table_b, lang_val):
        with session.lock:
            report = session.last_report
        if not report:
            return dc(lang_val, "dc_error"), gr.update()
        try:
            _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            def _safe(name: str) -> str:
                return re.sub(r"[^0-9A-Za-z_\-一-鿿]", "_",
                              str(name or ""))[:40]

            # table names in the filename so the load dropdown is findable
            # ("compare_20260929_*.json 一堆数字不知道谁是谁")
            pair = (f"{_safe(table_a)}_vs_{_safe(table_b)}_"
                    if table_a and table_b else "")
            fpath = _REPORTS_DIR / f"compare_{pair}{ts}.json"
            data = report.to_dict()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # refresh the load dropdown so the new file is pickable at once
            return (f'✅ {dc(lang_val, "dc_saved")} — {fpath.name}',
                    _list_reports())
        except Exception as e:
            return f'❌ {dc(lang_val, "dc_error")}: {_esc_html(str(e))}', gr.update()

    def _list_reports():
        # never touch `value`: setting it (even to None) fires load_dd's
        # .change, whose handler overwrites the result panel — saving a
        # report used to wipe the comparison the user had just rendered
        if not _REPORTS_DIR.is_dir():
            return gr.update(choices=[])
        files = sorted(_REPORTS_DIR.glob("compare_*.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        names = [f.name for f in files[:_MAX_REPORT_FILES]]
        return gr.update(choices=names)

    def _load_report(filename, lang_val):
        if not filename:
            return dc(lang_val, "dc_no_reports")
        fpath = _REPORTS_DIR / filename
        if not fpath.is_file():
            return dc(lang_val, "dc_no_reports")
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            report = CompareReport.from_dict(data)
            with session.lock:
                session.last_report = report

            parts: list[str] = []
            parts.append(f'<div style="color:#16a34a;font-weight:600;margin-bottom:8px;">'
                         f'✅ {dc(lang_val, "dc_loaded")} — {_esc_html(filename)}</div>')
            if report.schema is not None:
                parts.append(build_schema_diff_card(report.schema, lang_val))
            if report.row_count is not None:
                parts.append(build_count_card(report.row_count, lang_val))
            if report.aggregate is not None:
                parts.append(build_aggregate_card(report.aggregate, lang_val))
            if report.profile is not None:
                parts.append(build_profile_card(report.profile, lang_val))
            if report.skew is not None:
                parts.append(build_skew_card(report.skew, lang_val))
            if report.checksum is not None:
                parts.append(build_checksum_card(report.checksum, lang_val))
            if report.partition is not None:
                parts.append(build_partition_card(report.partition, lang_val))
            if report.custom_agg is not None:
                parts.append(build_custom_agg_card(report.custom_agg, lang_val))
            if report.chunked is not None:
                parts.append(build_chunked_card(report.chunked, lang_val))
            if report.keyed_diff is not None:
                parts.append(build_keyed_diff_card(report.keyed_diff, lang_val))
            if report.batch_counts is not None:
                parts.append(build_batch_count_card(report.batch_counts, lang_val))
            return "\n".join(parts) if parts else dc(lang_val, "dc_no_reports")
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Export ──

    def _export_csv(lang_val):
        with session.lock:
            report = session.last_report
        if not report:
            raise gr.Error(dc(lang_val, "dc_no_reports"))
        try:
            return _export_report_csv(report)
        except Exception as e:
            _log.warning("CSV export failed", exc_info=True)
            raise gr.Error(f"{dc(lang_val, 'dc_error')}: {e}") from e

    def _export_excel(lang_val):
        with session.lock:
            report = session.last_report
        if not report:
            raise gr.Error(dc(lang_val, "dc_no_reports"))
        try:
            return _export_report_excel(report)
        except Exception as e:
            _log.warning("Excel export failed", exc_info=True)
            raise gr.Error(f"{dc(lang_val, 'dc_error')}: {e}") from e

    # ── Connection presets (A) ──

    def _refresh_presets():
        names = [d["name"] for d in _PRESETS_STORE.list()]
        return gr.update(choices=names, value=None), gr.update(choices=names, value=None)

    def _save_preset(name, ds_label, host, port, db, user, pwd, env_val, lang_val):
        # Hidden auth/host textboxes submit None from the browser, not "".
        name = (name or "").strip()
        if not name:
            return dc(lang_val, "dc_error")
        ds_type = _DS_LABEL_TO_KEY.get(ds_label)
        if ds_type is None:
            return f"❌ {dc(lang_val, 'dc_error')}: unknown datasource {_esc_html(str(ds_label))}"
        try:
            port_int = int(port) if port else 0
        except ValueError:
            port_int = 0
        try:
            _PRESETS_STORE.save(name, ds_type, (host or "").strip(), port_int,
                                (db or "").strip(), (user or "").strip(),
                                (pwd or "").strip(),
                                environment=env_val.strip() if env_val else "")
            return f"✅ {dc(lang_val, 'dc_preset_saved')}: {_esc_html(name)}"
        except Exception as e:
            return _error_html(lang_val, e)

    def _load_preset(name, lang_val):
        if not name:
            return [gr.update()] * 7
        try:
            preset = _PRESETS_STORE.get_by_name(name)
            if not preset:
                return [gr.update()] * 7
            dialect = DIALECT_NAMES.get(preset["ds_type"], preset["ds_type"])
            return (
                gr.update(value=dialect),
                gr.update(value=preset.get("host", "")),
                gr.update(value=str(preset.get("port", ""))),
                gr.update(value=preset.get("database", "")),
                gr.update(value=preset.get("username", "")),
                gr.update(value=preset.get("password", "")),
                gr.update(value=preset.get("environment", "")),
            )
        except Exception:
            _log.warning("Failed to load preset: %s", name, exc_info=True)
            return [gr.update()] * 7

    def _delete_preset(name, lang_val):
        if not name:
            return dc(lang_val, "dc_preset_no_presets")
        try:
            presets = _PRESETS_STORE.list()
            for p in presets:
                if p["name"] == name:
                    _PRESETS_STORE.delete(p["id"])
                    return f"✅ {dc(lang_val, 'dc_preset_deleted')}"
            return dc(lang_val, "dc_preset_no_presets")
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Batch full comparison (F) ──

    def _batch_full(lang_val, where_val, threshold_str, progress=gr.Progress()):
        with session.lock:
            if session.executor_a is None or session.executor_b is None:
                return dc(lang_val, "dc_connect_both")
            tables_a = list(session.tables_a)
            tables_b = list(session.tables_b)

        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg

        threshold = parse_threshold(threshold_str)

        try:
            pairs = find_common_tables(tables_a, tables_b)
            if not pairs:
                return (
                    '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
                    'background:#f9fafb;margin-bottom:8px;">'
                    f'<b style="color:#6b7280;">{dc(lang_val, "dc_batch_full_result")}</b> — '
                    f'{dc(lang_val, "dc_no_common")}</div>'
                )

            items: list[BatchFullItem] = []
            total = len(pairs)
            for idx, (ta, tb) in enumerate(pairs):
                progress((idx + 1) / total,
                         desc=dc(lang_val, "dc_comparing_table").format(name=ta))
                try:
                    schema_r, _ = _schema_inner(ta, tb, lang_val, where_val)
                except Exception:
                    schema_r = None
                try:
                    count_r, _ = _count_inner(ta, tb, lang_val, where_val)
                except Exception:
                    count_r = None
                try:
                    agg_r, _ = _agg_inner(ta, tb, lang_val, where_val)
                except Exception:
                    agg_r = None

                has_diffs = False
                if schema_r and schema_r.has_changes:
                    has_diffs = True
                if count_r and count_r.delta != 0:
                    has_diffs = True
                if agg_r and agg_r.mismatches > 0:
                    has_diffs = True

                items.append(BatchFullItem(ta, tb, schema_r, count_r, agg_r, has_diffs))

            _store_partial("batch_full", items)
            return build_batch_full_card(items, lang_val, threshold)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── SeaTunnel sync config (C) ──

    def _gen_sync_config(table_a, table_b, col_mapping_str, lang_val):
        with session.lock:
            ex_a = session.executor_a
            ex_b = session.executor_b
        if not ex_a or not ex_b:
            return dc(lang_val, "dc_connect_both"), gr.update(visible=False)
        if not table_a or not table_b:
            return dc(lang_val, "dc_select_tables"), gr.update(visible=False)
        try:
            cfg_a, cfg_b = ex_a.config, ex_b.config
            mapping = parse_column_mapping(col_mapping_str) if col_mapping_str else None

            def _gen(pwd_a, pwd_b):
                return generate_sync_config(
                    cfg_a.ds_type, cfg_a.host, cfg_a.port, cfg_a.database,
                    cfg_a.username, pwd_a, table_a,
                    cfg_b.ds_type, cfg_b.host, cfg_b.port, cfg_b.database,
                    cfg_b.username, pwd_b, table_b,
                    column_mapping=mapping,
                )

            # Page shows a masked config; the real passwords only go to the
            # downloadable file so they never land in the rendered HTML.
            masked_text = _gen(
                "******" if cfg_a.password else None,
                "******" if cfg_b.password else None,
            )
            full_text = _gen(cfg_a.password, cfg_b.password)
            fd, tmp_path = tempfile.mkstemp(prefix="seatunnel_sync_", suffix=".conf")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(full_text)

            header = f'<div style="color:#16a34a;font-weight:600;margin-bottom:8px;">✅ {dc(lang_val, "dc_sync_generated")}</div>'
            code_block = f'<pre style="background:#1e293b;color:#e2e8f0;padding:16px;border-radius:8px;overflow-x:auto;font-size:12px;">{_esc_html(masked_text)}</pre>'
            return header + code_block, gr.update(value=tmp_path, visible=True)
        except Exception as e:
            return _error_html(lang_val, e), gr.update(visible=False)

    # ── Scheduled comparison (E) ──

    def _schedule_tick(table_a, table_b, lang_val, where_val, key_cols_str, interval_min,
                       threshold_str="", webhook_url="", notify_on_fail=False):
        """Background timer callback — run comparison and reschedule."""
        try:
            _compare_all(table_a, table_b, lang_val, where_val, key_cols_str,
                         threshold_str=threshold_str,
                         webhook_url=webhook_url,
                         notify_on_fail=bool(notify_on_fail))
            _save_report(lang_val)
            with session.lock:
                session.schedule_last_run = datetime.now(timezone.utc).strftime("%H:%M:%S")
                session.schedule_last_error = None
        except Exception as exc:
            _log.warning("Scheduled comparison failed", exc_info=True)
            with session.lock:
                session.schedule_last_error = str(exc)
            if webhook_url and webhook_url.strip():
                _send_webhook(webhook_url.strip(), {
                    "event": "scheduled_comparison_error",
                    "table_a": table_a, "table_b": table_b,
                    "error": str(exc),
                })
        with session.lock:
            if session.schedule_active:
                t = threading.Timer(
                    float(interval_min) * 60,
                    _schedule_tick,
                    args=(table_a, table_b, lang_val, where_val, key_cols_str,
                          interval_min, threshold_str, webhook_url, notify_on_fail),
                )
                t.daemon = True
                session.schedule_timer = t
                t.start()

    def _schedule_start(table_a, table_b, lang_val, where_val, key_cols_str, interval_str,
                        threshold_str="", webhook_url="", notify_on_fail=False):
        if not table_a or not table_b:
            return dc(lang_val, "dc_select_tables")
        try:
            interval_min = int(interval_str)
        except (ValueError, TypeError):
            interval_min = _DEFAULT_SCHEDULE_MIN
        interval_min = max(1, interval_min)
        with session.lock:
            if session.schedule_active:
                return dc(lang_val, "dc_schedule_running").format(m=interval_min)
            session.schedule_active = True
        t = threading.Timer(
            float(interval_min) * 60,
            _schedule_tick,
            args=(table_a, table_b, lang_val, where_val, key_cols_str,
                  interval_min, threshold_str, webhook_url, notify_on_fail),
        )
        t.daemon = True
        with session.lock:
            session.schedule_timer = t
        t.start()
        return f'✅ {dc(lang_val, "dc_schedule_running").format(m=interval_min)}'

    def _schedule_stop(lang_val):
        with session.lock:
            session.schedule_active = False
            timer = session.schedule_timer
            if timer:
                timer.cancel()
                session.schedule_timer = None
        return dc(lang_val, "dc_schedule_stopped")

    # ── History trends (H) ──

    def _show_trend(lang_val, alert_rules_raw=""):
        entries = build_trend_data(_REPORTS_DIR)
        if not entries:
            return dc(lang_val, "dc_trend_no_data"), gr.update(visible=False)
        try:
            plt = _get_matplotlib()
            # A 4th subplot for skew drift, only when any report measured skew
            has_skew = any(e.get("skew_top1") is not None for e in entries)
            n_plots = 4 if has_skew else 3
            fig, axes = plt.subplots(n_plots, 1,
                                     figsize=(8, 3 * n_plots), sharex=True)
            timestamps = [e["timestamp"] for e in entries]
            x = range(len(timestamps))

            # Subplot 1: Row Count Delta (line)
            deltas = [e["delta"] for e in entries]
            axes[0].plot(x, deltas, marker="o", color="#4C78A8",
                         linewidth=2, markersize=5)
            axes[0].set_ylabel("Row Count Delta")
            axes[0].set_title(dc(lang_val, "dc_trend_chart"))
            axes[0].axhline(y=0, color="#94a3b8", linestyle="--", linewidth=0.8)
            axes[0].grid(True, alpha=0.3)

            # Subplot 2: Aggregate Mismatches (bar)
            mismatches = [e.get("mismatches", 0) for e in entries]
            axes[1].bar(x, mismatches, color="#f59e0b", alpha=0.8)
            axes[1].set_ylabel(dc(lang_val, "dc_trend_mismatches"))
            axes[1].grid(True, alpha=0.3)

            # Subplot 3: Schema Changes (bar)
            schema_changes = [e.get("schema_changes", 0) for e in entries]
            axes[2].bar(x, schema_changes, color="#ef4444", alpha=0.8)
            axes[2].set_ylabel(dc(lang_val, "dc_trend_schema"))
            axes[2].grid(True, alpha=0.3)

            # Subplot 4: Skew Top-1 % (distribution drift; gaps where the
            # report carried no skew analysis)
            if has_skew:
                top1s = [e.get("skew_top1") for e in entries]
                axes[3].plot(x, [v if v is not None else float("nan")
                                 for v in top1s],
                             marker="o", color="#8b5cf6",
                             linewidth=2, markersize=5)
                axes[3].set_ylabel(dc(lang_val, "dc_trend_skew"))
                axes[3].set_ylim(0, 100)
                axes[3].axhline(y=50, color="#dc2626", linestyle="--",
                                linewidth=0.8)
                axes[3].grid(True, alpha=0.3)

            last = axes[n_plots - 1]
            last.set_xticks(list(x))
            last.set_xticklabels(timestamps, rotation=45, ha="right", fontsize=8)

            fig.set_facecolor("#fafafa")
            fig.tight_layout()
            info = dc(lang_val, "dc_history_count").format(n=len(entries))

            if alert_rules_raw and alert_rules_raw.strip():
                rules = parse_alert_rules(alert_rules_raw)
                if rules:
                    alerts = check_trend_alerts(entries, rules)
                    info += "<br>" + build_trend_alert_card(alerts, lang_val)

            return info, gr.update(visible=True, value=fig)
        except Exception as e:
            return f'❌ {_esc_html(str(e))}', gr.update(visible=False)

    # ── Report diff (Phase 5A) ──

    def _compare_reports_fn(old_name, new_name, lang_val):
        if not old_name or not new_name:
            return dc(lang_val, "dc_report_diff")
        try:
            old_path = _REPORTS_DIR / old_name
            new_path = _REPORTS_DIR / new_name
            if not old_path.is_file() or not new_path.is_file():
                return dc(lang_val, "dc_no_reports")
            with open(old_path, encoding="utf-8") as f:
                old_report = CompareReport.from_dict(json.load(f))
            with open(new_path, encoding="utf-8") as f:
                new_report = CompareReport.from_dict(json.load(f))
            rdiff = diff_reports(old_report, new_report)
            return build_report_diff_card(rdiff, lang_val)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Data lineage (Phase 5C) ──

    def _show_lineage_fn(table_a, lang_val, lineage_sql_str):
        if not table_a:
            return dc(lang_val, "dc_select_tables")
        if not lineage_sql_str or not lineage_sql_str.strip():
            return dc(lang_val, "dc_lineage_hint")
        try:
            sqls = [s.strip() for s in lineage_sql_str.strip().split("\n") if s.strip()]
            upstream = get_upstream_tables(table_a, sqls)
            return build_lineage_card(table_a, upstream, lang_val)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Feature A — Incremental comparison ──

    def _incremental_fn(table_a, table_b, lang_val, where_val,
                        watermark_col, watermark_val, key_cols_str,
                        col_mapping_str, masking_on):
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
            ex_a, ex_b = session.executor_a, session.executor_b
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
            key_cols = [k.strip() for k in key_cols_str.split(",") if k.strip()] if key_cols_str else []
            if key_cols:
                kd_result = diff_by_key(ra.columns, rows_a, rb_cols, rows_b, key_cols)
                _store_partial("keyed_diff", kd_result)
                return build_keyed_diff_card(kd_result, lang_val)
            diff = diff_results(ra.columns, rows_a, rb_cols, rows_b)
            _store_partial("sample", diff)
            return build_sample_diff_card(diff, lang_val, columns=ra.columns or rb_cols)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Feature B — Quality rules ──

    def _check_quality_fn(table_a, table_b, lang_val, where_val, quality_rules_str):
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
            profile_result, _ = _profile_inner(table_a, table_b, lang_val, where_val)
            results_a = check_quality_rules(rules, profile_result, side="a")
            results_b = check_quality_rules(rules, profile_result, side="b")
            return (build_quality_card(results_a, lang_val, side_label="A")
                    + build_quality_card(results_b, lang_val, side_label="B"))
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Feature C — Diff SQL generation ──

    def _gen_diff_sql_fn(table_a, table_b, lang_val):
        with session.lock:
            report = session.last_report
        if not report or not report.keyed_diff:
            return dc(lang_val, "dc_diff_sql_no_diff")
        try:
            with session.lock:
                ex_b = session.executor_b
            ds_type = ex_b.config.ds_type if ex_b else "mysql"
            sql = generate_diff_sql(report.keyed_diff, table_b, ds_type)
            return build_diff_sql_card(sql, lang_val)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── Feature D — Templates ──

    def _save_template(name, table_a, table_b, where_val, key_cols_str,
                       threshold_str, col_mapping_str, strategy, watermark_col,
                       quality_rules_str, webhook_url, notify_on_fail, masking_on, lang_val):
        if not name.strip():
            return dc(lang_val, "dc_error"), gr.update()
        try:
            _TEMPLATES_STORE.save(
                name=name.strip(), table_a=table_a or "", table_b=table_b or "",
                where_clause=where_val, key_columns=key_cols_str,
                threshold=threshold_str, column_mapping=col_mapping_str,
                sample_strategy=strategy, watermark_column=watermark_col,
                quality_rules=quality_rules_str, webhook_url=webhook_url,
                notify_on_fail=bool(notify_on_fail), masking_enabled=bool(masking_on),
            )
            names = [d["name"] for d in _TEMPLATES_STORE.list()]
            return f"✅ {dc(lang_val, 'dc_template_saved')}", gr.update(choices=names, value=None)
        except Exception as e:
            return _error_html(lang_val, e), gr.update()

    def _load_template(name, lang_val):
        if not name:
            return [gr.update()] * 12
        try:
            tmpl = _TEMPLATES_STORE.get_by_name(name)
            if not tmpl:
                return [gr.update()] * 12
            return (
                gr.update(value=tmpl.get("table_a", "")),
                gr.update(value=tmpl.get("table_b", "")),
                gr.update(value=tmpl.get("where_clause", "")),
                gr.update(value=tmpl.get("key_columns", "")),
                gr.update(value=tmpl.get("threshold", "")),
                gr.update(value=tmpl.get("column_mapping", "")),
                gr.update(value=tmpl.get("sample_strategy", "TOP N")),
                gr.update(value=tmpl.get("watermark_column", "")),
                gr.update(value=tmpl.get("quality_rules", "")),
                gr.update(value=tmpl.get("webhook_url", "")),
                gr.update(value=tmpl.get("notify_on_fail", False)),
                gr.update(value=tmpl.get("masking_enabled", True)),
            )
        except Exception:
            _log.warning("Failed to load template", exc_info=True)
            return [gr.update()] * 12

    def _delete_template(name, lang_val):
        if not name:
            return dc(lang_val, "dc_template_no_templates"), gr.update()
        try:
            for t in _TEMPLATES_STORE.list():
                if t["name"] == name:
                    _TEMPLATES_STORE.delete(t["id"])
                    names = [d["name"] for d in _TEMPLATES_STORE.list()]
                    return f"✅ {dc(lang_val, 'dc_template_deleted')}", gr.update(choices=names, value=None)
            return dc(lang_val, "dc_template_no_templates"), gr.update()
        except Exception as e:
            return _error_html(lang_val, e), gr.update()

    # ── Feature F6 — Batch template orchestration ──

    def _batch_templates_fn(selected_names, lang_val):
        if not selected_names:
            return dc(lang_val, "dc_batch_templates_hint")
        with session.lock:
            ex_a = session.executor_a
            ex_b = session.executor_b
        if ex_a is None or ex_b is None:
            return dc(lang_val, "dc_connect_both")
        results = []
        for name in selected_names:
            tmpl = _TEMPLATES_STORE.get_by_name(name)
            if not tmpl:
                results.append({"name": name, "status": "skip", "detail": "not found"})
                continue
            try:
                ta = tmpl.get("table_a", "")
                tb = tmpl.get("table_b", "")
                wh = tmpl.get("where_clause", "")

                # Count comparison
                count_sql_a = build_count_sql(ta, wh)
                count_sql_b = build_count_sql(tb, wh)
                ra, rb = run_parallel(
                    lambda s=count_sql_a: ex_a.run(s, max_rows=1),
                    lambda s=count_sql_b: ex_b.run(s, max_rows=1),
                )
                cnt_a = int(ra.rows[0][0]) if ra.rows else 0
                cnt_b = int(rb.rows[0][0]) if rb.rows else 0

                # Schema comparison
                schema_changes = 0
                try:
                    desc_a, desc_b = run_parallel(
                        lambda t=ta: ex_a.describe_table(t),
                        lambda t=tb: ex_b.describe_table(t),
                    )
                    ca_list = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
                    cb_list = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
                    schema_result = compare_schemas(ca_list, cb_list, ta, tb)
                    schema_changes = len(schema_result.items) if schema_result.has_changes else 0
                except Exception:
                    _log.warning("Batch template %r: schema comparison failed",
                                 name, exc_info=True)
                    desc_a = desc_b = None

                # Aggregate comparison on shared numeric columns
                agg_mismatches = 0
                try:
                    if desc_a and desc_b:
                        names_b = {c.name.lower() for c in desc_b.columns}
                        shared_num = [
                            c.name for c in desc_a.columns
                            if is_numeric_type(c.dtype) and c.name.lower() in names_b
                        ]
                        if shared_num:
                            agg_sql_a = build_aggregate_sql(
                                ta, shared_num[:_MAX_AGG_COLUMNS], wh,
                                ds_type=ex_a.config.ds_type)
                            agg_sql_b = build_aggregate_sql(
                                tb, shared_num[:_MAX_AGG_COLUMNS], wh,
                                ds_type=ex_b.config.ds_type)
                            agg_ra, agg_rb = run_parallel(
                                lambda s=agg_sql_a: ex_a.run(s, max_rows=200),
                                lambda s=agg_sql_b: ex_b.run(s, max_rows=200),
                            )
                            agg_result = compare_aggregates(
                                ta, agg_ra.rows[0] if agg_ra.rows else (),
                                tb, agg_rb.rows[0] if agg_rb.rows else (),
                                shared_num[:_MAX_AGG_COLUMNS],
                            )
                            agg_mismatches = agg_result.mismatches
                except Exception:
                    _log.warning("Batch template %r: aggregate comparison failed",
                                 name, exc_info=True)

                passed = cnt_a == cnt_b and schema_changes == 0 and agg_mismatches == 0
                results.append({
                    "name": name, "table_a": ta, "table_b": tb,
                    "count_a": cnt_a, "count_b": cnt_b,
                    "schema_changes": schema_changes,
                    "agg_mismatches": agg_mismatches,
                    "status": "pass" if passed else "fail",
                })
            except Exception as exc:
                results.append({"name": name, "status": "fail", "detail": str(exc)})
        return build_batch_template_card(results, lang_val)

    # ── Feature H — Multi-environment ──

    def _compare_environments_fn(env_a, env_b, table_name, lang_val, where_val):
        if not env_a.strip() or not env_b.strip():
            return dc(lang_val, "dc_env_hint")
        if not table_name.strip():
            return dc(lang_val, "dc_select_tables")
        ok, msg = _validate_where(where_val, lang_val)
        if not ok:
            return msg
        presets = _PRESETS_STORE.list()
        pa = next((p for p in presets if p.get("environment", "") == env_a.strip()), None)
        pb = next((p for p in presets if p.get("environment", "") == env_b.strip()), None)
        if not pa or not pb:
            return dc(lang_val, "dc_env_hint")
        try:
            cfg_a = DatabaseConfig(
                ds_type=pa["ds_type"], host=pa["host"], port=pa["port"],
                database=pa["database"], username=pa.get("username"),
                password=pa.get("password"),
            )
            cfg_b = DatabaseConfig(
                ds_type=pb["ds_type"], host=pb["host"], port=pb["port"],
                database=pb["database"], username=pb.get("username"),
                password=pb.get("password"),
            )
            ex_a = create_executor(cfg_a)
            ex_b = create_executor(cfg_b)
            tbl = table_name.strip()
            cards: list[str] = []
            label_a = f"{tbl} ({env_a})"
            label_b = f"{tbl} ({env_b})"

            # Schema comparison
            desc_a, desc_b = run_parallel(
                lambda: ex_a.describe_table(tbl),
                lambda: ex_b.describe_table(tbl),
            )
            ca_list = [{"name": c.name, "type": c.dtype} for c in desc_a.columns]
            cb_list = [{"name": c.name, "type": c.dtype} for c in desc_b.columns]
            schema_result = compare_schemas(ca_list, cb_list, label_a, label_b)
            cards.append(build_schema_diff_card(schema_result, lang_val))

            # Count comparison
            sql_ca = build_count_sql(tbl, where_val)
            sql_cb = build_count_sql(tbl, where_val)
            ra, rb = run_parallel(
                lambda: ex_a.run(sql_ca, max_rows=1),
                lambda: ex_b.run(sql_cb, max_rows=1),
            )
            ca = int(ra.rows[0][0]) if ra.rows else 0
            cb = int(rb.rows[0][0]) if rb.rows else 0
            count_result = build_row_count_result(label_a, ca, label_b, cb)
            cards.append(build_count_card(count_result, lang_val))

            # Aggregate comparison on shared numeric columns
            names_b = {c.name.lower() for c in desc_b.columns}
            shared_num = [
                c.name for c in desc_a.columns
                if is_numeric_type(c.dtype) and c.name.lower() in names_b
            ]
            if shared_num:
                agg_sql_a = build_aggregate_sql(tbl, shared_num[:_MAX_AGG_COLUMNS],
                                                where_val, ds_type=ex_a.config.ds_type)
                agg_sql_b = build_aggregate_sql(tbl, shared_num[:_MAX_AGG_COLUMNS],
                                                where_val, ds_type=ex_b.config.ds_type)
                agg_ra, agg_rb = run_parallel(
                    lambda: ex_a.run(agg_sql_a, max_rows=200),
                    lambda: ex_b.run(agg_sql_b, max_rows=200),
                )
                agg_result = compare_aggregates(
                    label_a, agg_ra.rows[0] if agg_ra.rows else (),
                    label_b, agg_rb.rows[0] if agg_rb.rows else (),
                    shared_num[:_MAX_AGG_COLUMNS],
                )
                cards.append(build_aggregate_card(agg_result, lang_val))

            header = f'<h4 style="color:#6366f1;">{dc(lang_val, "dc_env_compare_result")}</h4>'
            return header + "\n".join(cards)
        except Exception as e:
            return _error_html(lang_val, e)

    # ── DS type change handler ──
    def _on_ds_change(ds_label: str):
        ds = _DS_LABEL_TO_KEY.get(ds_label)
        if ds is None:
            return tuple(gr.update() for _ in range(5))
        defaults = DS_DEFAULTS[ds]
        default_port = str(defaults["port"])
        default_db = defaults["database"]
        show_auth = ds in _NEEDS_AUTH
        show_host = ds in _NEEDS_HOST
        env_cfg = config_from_env(ds)
        if env_cfg:
            return (
                gr.update(value=str(env_cfg.port), placeholder=default_port, visible=show_host),
                gr.update(value=env_cfg.database, placeholder=str(default_db)),
                gr.update(value=env_cfg.host, visible=show_host),
                gr.update(value=env_cfg.username or "", visible=show_auth),
                gr.update(value=env_cfg.password or "", visible=show_auth),
            )
        return (
            gr.update(value="", placeholder=default_port, visible=show_host),
            gr.update(value="", placeholder=str(default_db)),
            gr.update(value="", visible=show_host),
            gr.update(value="", visible=show_auth),
            gr.update(value="", visible=show_auth),
        )

    # ── Layout ──

    # marker: body:has(.st-dc-page) makes .st-main scroll internally
    gr.HTML('<div class="st-dc-page" style="display:none"></div>')

    with gr.Row(elem_classes=["st-page-row"]):
        lang_state = gr.State("en")

        # ── Left sidebar ──
        with gr.Column(scale=0, min_width=720,
                       elem_classes=["st-sidebar", "st-dc-sidebar"]):
            title_md = gr.Markdown(t("dc_title"))

            with gr.Row():
                # Source A panel
                with gr.Column(min_width=260):
                    src_a_md = gr.Markdown(f"**{t('dc_source_a')}**")
                    ds_a = gr.Dropdown(choices=_DS_CHOICES, value=_DS_CHOICES[0],
                                       label=t("dc_datasource_type"), elem_classes=["st-sidebar-control"])
                    host_a = gr.Textbox(label=t("dc_host"), placeholder="10.0.0.1",
                                        elem_classes=["st-sidebar-control"])
                    with gr.Row():
                        port_a = gr.Textbox(label=t("dc_port"), placeholder="10000",
                                            elem_classes=["st-sidebar-control"])
                        db_a = gr.Textbox(label=t("dc_database"), placeholder="default",
                                          elem_classes=["st-sidebar-control"])
                    user_a = gr.Textbox(label=t("dc_username"), visible=False,
                                        elem_classes=["st-sidebar-control"])
                    pwd_a = gr.Textbox(label=t("dc_password"), type="password", visible=False,
                                       elem_classes=["st-sidebar-control"])
                    conn_a = gr.Button(t("dc_connect"), variant="secondary", size="sm",
                                       elem_classes=["st-connect-btn"])
                    status_a = gr.Textbox(label=t("dc_status"), value=t("dc_not_connected"),
                                          interactive=False, elem_classes=["st-sidebar-status"])
                    table_a = gr.Dropdown(choices=[], label=t("dc_select_table"),
                                          filterable=True,
                                          elem_classes=["st-sidebar-control"])

                # Source B panel
                with gr.Column(min_width=260):
                    src_b_md = gr.Markdown(f"**{t('dc_source_b')}**")
                    ds_b = gr.Dropdown(choices=_DS_CHOICES, value=_DS_CHOICES[0],
                                       label=t("dc_datasource_type"), elem_classes=["st-sidebar-control"])
                    host_b = gr.Textbox(label=t("dc_host"), placeholder="10.0.0.1",
                                        elem_classes=["st-sidebar-control"])
                    with gr.Row():
                        port_b = gr.Textbox(label=t("dc_port"), placeholder="10000",
                                            elem_classes=["st-sidebar-control"])
                        db_b = gr.Textbox(label=t("dc_database"), placeholder="default",
                                          elem_classes=["st-sidebar-control"])
                    user_b = gr.Textbox(label=t("dc_username"), visible=False,
                                        elem_classes=["st-sidebar-control"])
                    pwd_b = gr.Textbox(label=t("dc_password"), type="password", visible=False,
                                       elem_classes=["st-sidebar-control"])
                    conn_b = gr.Button(t("dc_connect"), variant="secondary", size="sm",
                                       elem_classes=["st-connect-btn"])
                    status_b = gr.Textbox(label=t("dc_status"), value=t("dc_not_connected"),
                                          interactive=False, elem_classes=["st-sidebar-status"])
                    table_b = gr.Dropdown(choices=[], label=t("dc_select_table"),
                                          filterable=True,
                                          elem_classes=["st-sidebar-control"])

            # Connection presets (A)
            with gr.Accordion(t("dc_presets"), open=False) as presets_accordion:
                with gr.Row():
                    preset_name_input = gr.Textbox(label=t("dc_preset_name"), scale=2,
                                                    elem_classes=["st-sidebar-control"])
                    preset_env_input = gr.Textbox(label=t("dc_preset_env"), scale=1,
                                                   elem_classes=["st-sidebar-control"])
                    preset_save_btn = gr.Button(f'{t("dc_preset_save")} (A)', size="sm",
                                                 elem_classes=["st-connect-btn"])
                    preset_save_b_btn = gr.Button(f'{t("dc_preset_save")} (B)', size="sm",
                                                   elem_classes=["st-connect-btn"])
                with gr.Row():
                    preset_dd_a = gr.Dropdown(choices=[], label=f"{t('dc_preset_load')} (A)",
                                               elem_classes=["st-sidebar-control"])
                    preset_dd_b = gr.Dropdown(choices=[], label=f"{t('dc_preset_load')} (B)",
                                               elem_classes=["st-sidebar-control"])
                    preset_delete_btn = gr.Button("🗑", size="sm",
                                                   elem_classes=["st-connect-btn"])
                preset_status = gr.HTML("")

            # D — WHERE filter
            where_input = gr.Textbox(label=t("dc_where_clause"),
                                      placeholder=t("dc_where_hint"),
                                      elem_classes=["st-sidebar-control"])

            # B — Threshold
            threshold_input = gr.Textbox(label=t("dc_threshold"),
                                          placeholder=t("dc_threshold_hint"),
                                          elem_classes=["st-sidebar-control"])

            # A — Key columns
            key_input = gr.Textbox(label=t("dc_key_columns"),
                                    placeholder="id, order_id",
                                    elem_classes=["st-sidebar-control"])

            # D — Column mapping
            mapping_input = gr.Textbox(label=t("dc_col_mapping"),
                                        placeholder=t("dc_col_mapping_hint"),
                                        elem_classes=["st-sidebar-control"])

            # G — Sampling strategy
            with gr.Row():
                sample_strategy = gr.Dropdown(
                    choices=_SAMPLE_STRATEGIES, value="TOP N",
                    label=t("dc_sample_strategy"),
                    elem_classes=["st-sidebar-control"])
                stratified_col_input = gr.Textbox(
                    label=t("dc_stratified_col"),
                    placeholder=t("dc_stratified_col_hint"),
                    visible=False,
                    elem_classes=["st-sidebar-control"])

            # Feature G — Data masking
            masking_checkbox = gr.Checkbox(label=t("dc_masking_enabled"), value=True)

            # One-click undo for every optional compare feature: clearing a
            # dozen textboxes by hand to get back to a plain compare was the
            # only way to "deselect" features before.
            reset_options_btn = gr.Button(t("dc_reset_options"), size="sm",
                                          elem_classes=["st-connect-btn"])

            # Feature A — Incremental comparison
            with gr.Accordion(t("dc_incremental"), open=False) as incremental_accordion:
                watermark_col_input = gr.Textbox(
                    label=t("dc_watermark_col"),
                    placeholder=t("dc_watermark_hint"),
                    elem_classes=["st-sidebar-control"])
                watermark_val_input = gr.Textbox(
                    label=t("dc_watermark_value"),
                    placeholder="2024-01-01 00:00:00",
                    elem_classes=["st-sidebar-control"])
                incremental_btn = gr.Button(
                    t("dc_incremental_compare"), size="sm",
                    elem_classes=["st-connect-btn"])

            # Feature B — Quality rules
            with gr.Accordion(t("dc_quality"), open=False) as quality_accordion:
                quality_rules_input = gr.Textbox(
                    label=t("dc_quality_rules"),
                    placeholder=t("dc_quality_rules_hint"),
                    elem_classes=["st-sidebar-control"])
                quality_btn = gr.Button(
                    t("dc_quality_check"), size="sm",
                    elem_classes=["st-connect-btn"])

            # BB — Data Skew
            with gr.Accordion(t("dc_skew"), open=False) as skew_accordion:
                skew_cols_input = gr.Textbox(
                    label=t("dc_skew_column"),
                    placeholder=t("dc_skew_columns_hint"),
                    elem_classes=["st-sidebar-control"])
                skew_btn = gr.Button(
                    t("dc_skew_analyze"), size="sm",
                    elem_classes=["st-connect-btn"])

            with gr.Accordion(t("dc_checksum"), open=False) as checksum_accordion:
                checksum_cols_input = gr.Textbox(
                    label=t("dc_checksum"),
                    placeholder=t("dc_checksum_columns_hint"),
                    elem_classes=["st-sidebar-control"])
                checksum_btn = gr.Button(
                    t("dc_checksum_analyze"), size="sm",
                    elem_classes=["st-connect-btn"])
                # chunked verification (uses Key Columns as the numeric PK)
                chunked_btn = gr.Button(
                    t("dc_chunked_btn"), size="sm",
                    elem_classes=["st-connect-btn"])

            with gr.Accordion(t("dc_partition"), open=False) as partition_accordion:
                partition_col_input = gr.Textbox(
                    label=t("dc_partition_col"),
                    placeholder=t("dc_partition_col_hint"),
                    elem_classes=["st-sidebar-control"])
                partition_btn = gr.Button(
                    t("dc_partition_analyze"), size="sm",
                    elem_classes=["st-connect-btn"])

            with gr.Accordion(t("dc_custom_agg"), open=False) as custom_agg_accordion:
                custom_agg_input = gr.Textbox(
                    label=t("dc_custom_agg"),
                    placeholder=t("dc_custom_agg_hint"),
                    lines=3,
                    elem_classes=["st-sidebar-control"])
                custom_agg_btn = gr.Button(
                    t("dc_custom_agg_analyze"), size="sm",
                    elem_classes=["st-connect-btn"])

            gr.Markdown("---")
            with gr.Row():
                schema_btn = gr.Button(t("dc_compare_schema"), size="sm", elem_classes=["st-connect-btn"])
                count_btn = gr.Button(t("dc_compare_count"), size="sm", elem_classes=["st-connect-btn"])
                sample_btn = gr.Button(t("dc_compare_sample"), size="sm", elem_classes=["st-connect-btn"])
                agg_btn = gr.Button(t("dc_compare_agg"), size="sm", elem_classes=["st-connect-btn"])
            with gr.Row():
                all_btn = gr.Button(t("dc_compare_all"), variant="primary", size="sm",
                                    elem_classes=["st-connect-btn"])
                batch_btn = gr.Button(t("dc_batch_count"), size="sm",
                                      elem_classes=["st-connect-btn"])
                profile_btn = gr.Button(t("dc_profile"), size="sm",
                                        elem_classes=["st-connect-btn"])
                batch_full_btn = gr.Button(t("dc_batch_full"), size="sm",
                                            elem_classes=["st-connect-btn"])

            # Custom SQL
            with gr.Accordion(t("dc_custom_sql"), open=False) as sql_accordion:
                sql_a_input = gr.Textbox(label="SQL (A)", placeholder=t("dc_sql_placeholder"),
                                          lines=3, elem_classes=["st-sidebar-control"])
                sql_b_input = gr.Textbox(label="SQL (B)", placeholder=t("dc_sql_placeholder"),
                                          lines=3, elem_classes=["st-sidebar-control"])
                sql_btn = gr.Button(t("dc_compare_sql"), size="sm", elem_classes=["st-connect-btn"])

            # C — Sync config + Diff SQL
            with gr.Accordion(t("dc_gen_sync"), open=False) as sync_accordion:
                gen_sync_btn = gr.Button(t("dc_gen_sync"), size="sm",
                                          elem_classes=["st-connect-btn"])
                sync_download_btn = gr.DownloadButton(
                    "⬇ config (.conf)", size="sm", visible=False,
                    elem_classes=["st-connect-btn"])
                gen_diff_sql_btn = gr.Button(t("dc_gen_diff_sql"), size="sm",
                                              elem_classes=["st-connect-btn"])

            # D — Templates
            with gr.Accordion(t("dc_templates"), open=False) as templates_accordion:
                template_name_input = gr.Textbox(
                    label=t("dc_template_name"),
                    elem_classes=["st-sidebar-control"])
                template_save_btn = gr.Button(
                    t("dc_template_save"), size="sm",
                    elem_classes=["st-connect-btn"])
                template_dd = gr.Dropdown(
                    choices=[], label=t("dc_template_load"),
                    elem_classes=["st-sidebar-control"])
                with gr.Row():
                    template_load_btn = gr.Button(
                        t("dc_template_load"), size="sm",
                        elem_classes=["st-connect-btn"])
                    template_delete_btn = gr.Button(
                        "🗑", size="sm",
                        elem_classes=["st-connect-btn"])
                template_status = gr.HTML("")
                # F6 — Batch template orchestration
                batch_template_dd = gr.Dropdown(
                    choices=[], label=t("dc_batch_templates"),
                    multiselect=True,
                    elem_classes=["st-sidebar-control"])
                batch_template_btn = gr.Button(
                    t("dc_batch_templates_run"), size="sm",
                    elem_classes=["st-connect-btn"])

            # E — Schedule
            with gr.Accordion(t("dc_schedule"), open=False) as schedule_accordion:
                schedule_interval = gr.Dropdown(
                    choices=["1", "5", "15", "30", "60"], value="15",
                    label=t("dc_schedule_interval"),
                    elem_classes=["st-sidebar-control"])
                with gr.Row():
                    schedule_start_btn = gr.Button(t("dc_schedule_start"), size="sm",
                                                    elem_classes=["st-connect-btn"])
                    schedule_stop_btn = gr.Button(t("dc_schedule_stop"), size="sm",
                                                   elem_classes=["st-connect-btn"])
                schedule_status = gr.HTML("")

            # X — Webhook
            with gr.Accordion(t("dc_webhook"), open=False) as webhook_accordion:
                webhook_url_input = gr.Textbox(
                    label=t("dc_webhook_url"),
                    placeholder=t("dc_webhook_url_hint"),
                    elem_classes=["st-sidebar-control"])
                webhook_on_fail = gr.Checkbox(
                    label=t("dc_webhook_on_fail"), value=False)

            # H — Trends
            with gr.Accordion(t("dc_trend"), open=False) as trend_accordion:
                alert_rules_input = gr.Textbox(
                    label=t("dc_alert_rules"),
                    placeholder=t("dc_alert_rules_hint"),
                    elem_classes=["st-sidebar-control"])
                trend_btn = gr.Button(t("dc_trend_chart"), size="sm",
                                       elem_classes=["st-connect-btn"])
                # Report diff (Phase 5A)
                with gr.Row():
                    report_old_dd = gr.Dropdown(choices=[], label=t("dc_report_old"),
                                                 filterable=True,
                                                 elem_classes=["st-sidebar-control"])
                    report_new_dd = gr.Dropdown(choices=[], label=t("dc_report_new"),
                                                 filterable=True,
                                                 elem_classes=["st-sidebar-control"])
                report_diff_btn = gr.Button(t("dc_report_compare"), size="sm",
                                             elem_classes=["st-connect-btn"])

            # Data lineage (Phase 5C)
            with gr.Accordion(t("dc_lineage_title"), open=False) as lineage_accordion:
                lineage_sql_input = gr.Textbox(
                    label=t("dc_lineage_hint"),
                    placeholder="SELECT * FROM source_table ...",
                    lines=3,
                    elem_classes=["st-sidebar-control"])
                lineage_btn = gr.Button(t("dc_lineage_title"), size="sm",
                                         elem_classes=["st-connect-btn"])

            # AA — Multi-environment
            with gr.Accordion(t("dc_environment"), open=False) as env_accordion:
                with gr.Row():
                    env_input_a = gr.Textbox(
                        label=t("dc_env_a"),
                        placeholder=t("dc_env_hint"),
                        elem_classes=["st-sidebar-control"])
                    env_input_b = gr.Textbox(
                        label=t("dc_env_b"),
                        placeholder=t("dc_env_hint"),
                        elem_classes=["st-sidebar-control"])
                env_table_input = gr.Textbox(
                    label=t("dc_select_table"),
                    placeholder="orders",
                    elem_classes=["st-sidebar-control"])
                env_compare_btn = gr.Button(
                    t("dc_compare_envs"), size="sm",
                    elem_classes=["st-connect-btn"])

            with gr.Row():
                csv_btn = gr.DownloadButton(t("dc_export_csv"), size="sm",
                                             elem_classes=["st-connect-btn"])
                excel_btn = gr.DownloadButton(t("dc_export_excel"), size="sm",
                                               elem_classes=["st-connect-btn"])
                view_btn = gr.Button(t("dc_view_report"), size="sm", variant="secondary",
                                     elem_classes=["st-connect-btn"])

            # Report persistence
            with gr.Row():
                save_btn = gr.Button(t("dc_save_report"), size="sm", elem_classes=["st-connect-btn"])
                load_dd = gr.Dropdown(choices=[], label=t("dc_load_report"),
                                       filterable=True,
                                       elem_classes=["st-sidebar-control"])
                load_btn = gr.Button("↻", size="sm", elem_classes=["st-connect-btn"])

        # ── Right main area ──
        with gr.Column(scale=1, elem_classes=["st-main"]):
            with gr.Row(elem_classes=["st-topbar-row"]):
                gr.HTML('<div class="st-topbar-spacer"></div>')
                home_btn = gr.Button("\U0001f3e0", size="sm", elem_classes=["st-home-btn"])
            save_status = gr.HTML(value="", visible=True)
            result_html = gr.HTML(
                value=(
                    '<div style="display:flex;align-items:center;justify-content:center;'
                    f'height:60vh;color:#9ca3af;font-size:15px;">'
                    f'{t("dc_placeholder")}</div>'
                ),
                elem_classes=["st-schema-card"],
            )
            hidden_report = gr.Textbox(visible=False, elem_id="dc-hidden-report")
            trend_plot = gr.Plot(label="", visible=False)

    # ── Wire callbacks ──

    # DS type changes
    ds_a.change(fn=_on_ds_change, inputs=[ds_a],
                outputs=[port_a, db_a, host_a, user_a, pwd_a])
    ds_b.change(fn=_on_ds_change, inputs=[ds_b],
                outputs=[port_b, db_b, host_b, user_b, pwd_b])

    # Connect buttons
    conn_a.click(
        fn=lambda *args: _do_connect(*args, side="a"),
        inputs=[ds_a, host_a, port_a, db_a, user_a, pwd_a, lang_state],
        outputs=[status_a, table_a, host_a, port_a, db_a],
    )
    conn_b.click(
        fn=lambda *args: _do_connect(*args, side="b"),
        inputs=[ds_b, host_b, port_b, db_b, user_b, pwd_b, lang_state],
        outputs=[status_b, table_b, host_b, port_b, db_b],
    )

    # Strategy change — show/hide stratified column input
    def _reset_options():
        """Restore every optional compare feature to its default — the
        one-click way to deselect features (connections and table picks
        stay untouched)."""
        return (
            gr.update(value=""),                    # where_input
            gr.update(value=""),                    # threshold_input
            gr.update(value=""),                    # key_input
            gr.update(value=""),                    # mapping_input
            gr.update(value="TOP N"),               # sample_strategy
            gr.update(value="", visible=False),     # stratified_col_input
            gr.update(value=True),                  # masking_checkbox
            gr.update(value=""),                    # watermark_col_input
            gr.update(value=""),                    # watermark_val_input
            gr.update(value=""),                    # quality_rules_input
            gr.update(value=""),                    # skew_cols_input
            gr.update(value=""),                    # checksum_cols_input
            gr.update(value=""),                    # partition_col_input
            gr.update(value=""),                    # custom_agg_input
            gr.update(value=""),                    # webhook_url_input
            gr.update(value=False),                 # webhook_on_fail
            gr.update(value=""),                    # alert_rules_input
            gr.update(value=""),                    # sql_a_input
            gr.update(value=""),                    # sql_b_input
            gr.update(value=""),                    # template_name_input
            gr.update(value=""),                    # preset_name_input
            gr.update(value=""),                    # preset_env_input
            gr.update(value="15"),                  # schedule_interval
            gr.update(value=""),                    # lineage_sql_input
            gr.update(value=""),                    # env_input_a
            gr.update(value=""),                    # env_input_b
            gr.update(value=""),                    # env_table_input
        )

    # NOTE: dropdowns that carry .change handlers (加载报告/模板/预设/批量模板)
    # are deliberately NOT reset — programmatic value changes would fire
    # their handlers (the load_dd result-wipe bug all over again).
    reset_options_btn.click(
        fn=_reset_options,
        outputs=[where_input, threshold_input, key_input, mapping_input,
                 sample_strategy, stratified_col_input, masking_checkbox,
                 watermark_col_input, watermark_val_input,
                 quality_rules_input, skew_cols_input, checksum_cols_input,
                 partition_col_input, custom_agg_input,
                 webhook_url_input, webhook_on_fail, alert_rules_input,
                 sql_a_input, sql_b_input, template_name_input,
                 preset_name_input, preset_env_input, schedule_interval,
                 lineage_sql_input, env_input_a, env_input_b,
                 env_table_input],
    )

    sample_strategy.change(
        fn=lambda s: gr.update(visible=(s == "STRATIFIED")),
        inputs=[sample_strategy],
        outputs=[stratified_col_input])

    # Compare buttons — pass threshold, strategy, mapping where applicable
    schema_btn.click(fn=_compare_schema,
                     inputs=[table_a, table_b, lang_state, where_input],
                     outputs=[result_html])
    count_btn.click(fn=_compare_count,
                    inputs=[table_a, table_b, lang_state, where_input, threshold_input],
                    outputs=[result_html])
    sample_btn.click(fn=_compare_sample,
                     inputs=[table_a, table_b, lang_state, where_input, key_input,
                             sample_strategy, mapping_input, masking_checkbox,
                             stratified_col_input],
                     outputs=[result_html])
    agg_btn.click(fn=_compare_agg,
                  inputs=[table_a, table_b, lang_state, where_input],
                  outputs=[result_html])
    # Compare All runs for ~20s on real warehouses; trigger_mode="once"
    # drops clicks while the event chain is pending, so an impatient
    # double-click cannot queue a duplicate run (observed in the wild: the
    # second run re-hit the DBs for nothing and repainted the result area).
    # A visual interactive=False chain was tried and reverted: the update
    # provably never reaches the button on multipage routes.
    all_btn.click(fn=_compare_all, trigger_mode="once",
                  inputs=[table_a, table_b, lang_state, where_input, key_input,
                          threshold_input, sample_strategy, mapping_input,
                          masking_checkbox, webhook_url_input, webhook_on_fail,
                          skew_cols_input, stratified_col_input,
                          checksum_cols_input, partition_col_input, custom_agg_input],
                  outputs=[result_html])
    batch_btn.click(fn=_batch_count,
                    inputs=[lang_state, where_input],
                    outputs=[result_html])
    profile_btn.click(fn=_compare_profile,
                      inputs=[table_a, table_b, lang_state, where_input],
                      outputs=[result_html])
    skew_btn.click(fn=_compare_skew,
                   inputs=[table_a, table_b, lang_state, where_input, skew_cols_input],
                   outputs=[result_html])
    checksum_btn.click(fn=_compare_checksum,
                       inputs=[table_a, table_b, lang_state, where_input, checksum_cols_input],
                       outputs=[result_html])
    chunked_btn.click(fn=_compare_chunked_btn_fn,
                      inputs=[table_a, table_b, lang_state, where_input,
                              key_input, checksum_cols_input, mapping_input],
                      outputs=[result_html])
    partition_btn.click(fn=_compare_partition,
                        inputs=[table_a, table_b, lang_state, where_input, partition_col_input],
                        outputs=[result_html])
    custom_agg_btn.click(fn=_compare_custom_agg,
                         inputs=[table_a, table_b, lang_state, where_input, custom_agg_input],
                         outputs=[result_html])
    # Same double-click guard as Compare All: batch full compare walks every
    # common table pair and is the slowest action on the page.
    batch_full_btn.click(fn=_batch_full, trigger_mode="once",
                         inputs=[lang_state, where_input, threshold_input],
                         outputs=[result_html])

    # B — Custom SQL
    sql_btn.click(fn=_compare_sql,
                  inputs=[sql_a_input, sql_b_input, lang_state],
                  outputs=[result_html])

    # C — Sync config + Diff SQL
    gen_sync_btn.click(fn=_gen_sync_config,
                       inputs=[table_a, table_b, mapping_input, lang_state],
                       outputs=[result_html, sync_download_btn])
    gen_diff_sql_btn.click(fn=_gen_diff_sql_fn,
                           inputs=[table_a, table_b, lang_state],
                           outputs=[result_html])

    # Feature A — Incremental
    incremental_btn.click(
        fn=_incremental_fn,
        inputs=[table_a, table_b, lang_state, where_input,
                watermark_col_input, watermark_val_input, key_input,
                mapping_input, masking_checkbox],
        outputs=[result_html],
    )

    # Feature B — Quality
    quality_btn.click(
        fn=_check_quality_fn,
        inputs=[table_a, table_b, lang_state, where_input, quality_rules_input],
        outputs=[result_html],
    )

    # Feature D — Templates
    template_save_btn.click(
        fn=_save_template,
        inputs=[template_name_input, table_a, table_b, where_input, key_input,
                threshold_input, mapping_input, sample_strategy, watermark_col_input,
                quality_rules_input, webhook_url_input, webhook_on_fail, masking_checkbox,
                lang_state],
        outputs=[template_status, template_dd],
    )
    template_load_btn.click(
        fn=_load_template,
        inputs=[template_dd, lang_state],
        outputs=[table_a, table_b, where_input, key_input, threshold_input,
                 mapping_input, sample_strategy, watermark_col_input,
                 quality_rules_input, webhook_url_input,
                 webhook_on_fail, masking_checkbox],
    )
    template_delete_btn.click(
        fn=_delete_template,
        inputs=[template_dd, lang_state],
        outputs=[template_status, template_dd],
    )

    # F6 — Batch template orchestration
    def _refresh_batch_template_choices():
        names = [d["name"] for d in _TEMPLATES_STORE.list()]
        return gr.update(choices=names)

    batch_template_dd.focus(fn=_refresh_batch_template_choices, outputs=[batch_template_dd])
    batch_template_btn.click(
        fn=_batch_templates_fn,
        inputs=[batch_template_dd, lang_state],
        outputs=[result_html],
    )

    # Feature H — Environment compare
    env_compare_btn.click(
        fn=_compare_environments_fn,
        inputs=[env_input_a, env_input_b, env_table_input, lang_state, where_input],
        outputs=[result_html],
    )

    # E — Schedule
    schedule_start_btn.click(
        fn=_schedule_start,
        inputs=[table_a, table_b, lang_state, where_input, key_input, schedule_interval,
                threshold_input, webhook_url_input, webhook_on_fail],
        outputs=[schedule_status],
    )
    schedule_stop_btn.click(fn=_schedule_stop, inputs=[lang_state],
                            outputs=[schedule_status])

    # H — Trends
    trend_btn.click(fn=_show_trend, inputs=[lang_state, alert_rules_input],
                    outputs=[result_html, trend_plot])

    # Report diff (Phase 5A)
    def _refresh_report_dds():
        if not _REPORTS_DIR.is_dir():
            return gr.update(choices=[]), gr.update(choices=[])
        files = sorted(_REPORTS_DIR.glob("compare_*.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        names = [f.name for f in files[:_MAX_REPORT_FILES]]
        return gr.update(choices=names), gr.update(choices=names)

    report_diff_btn.click(fn=_compare_reports_fn,
                          inputs=[report_old_dd, report_new_dd, lang_state],
                          outputs=[result_html])
    report_old_dd.focus(fn=_refresh_report_dds,
                        outputs=[report_old_dd, report_new_dd])

    # Data lineage (Phase 5C)
    lineage_btn.click(fn=_show_lineage_fn,
                      inputs=[table_a, lang_state, lineage_sql_input],
                      outputs=[result_html])

    # A — Presets
    def _save_and_refresh(name, ds_label, host, port, db, user, pwd, env_val,
                          lang_val):
        status = _save_preset(name, ds_label, host, port, db, user, pwd,
                              env_val, lang_val)
        dd_a, dd_b = _refresh_presets()
        return status, dd_a, dd_b

    preset_save_btn.click(
        fn=_save_and_refresh,
        inputs=[preset_name_input, ds_a, host_a, port_a, db_a, user_a, pwd_a, preset_env_input, lang_state],
        outputs=[preset_status, preset_dd_a, preset_dd_b],
    )
    preset_save_b_btn.click(
        fn=_save_and_refresh,
        inputs=[preset_name_input, ds_b, host_b, port_b, db_b, user_b, pwd_b, preset_env_input, lang_state],
        outputs=[preset_status, preset_dd_a, preset_dd_b],
    )
    # populate the load dropdowns when the accordion opens (presets saved in
    # earlier sessions were otherwise never listed — _refresh_presets had no
    # caller at all)
    presets_accordion.expand(
        fn=_refresh_presets, outputs=[preset_dd_a, preset_dd_b])
    def _delete_and_refresh(name, lang_val):
        status = _delete_preset(name, lang_val)
        dd_a, dd_b = _refresh_presets()
        return status, dd_a, dd_b

    preset_delete_btn.click(
        fn=_delete_and_refresh,
        inputs=[preset_dd_a, lang_state],
        outputs=[preset_status, preset_dd_a, preset_dd_b],
    )
    preset_dd_a.change(fn=_load_preset, inputs=[preset_dd_a, lang_state],
                       outputs=[ds_a, host_a, port_a, db_a, user_a, pwd_a, preset_env_input])
    preset_dd_b.change(fn=_load_preset, inputs=[preset_dd_b, lang_state],
                       outputs=[ds_b, host_b, port_b, db_b, user_b, pwd_b, preset_env_input])

    # Export buttons
    csv_btn.click(fn=_export_csv, inputs=[lang_state], outputs=[csv_btn])
    excel_btn.click(fn=_export_excel, inputs=[lang_state], outputs=[excel_btn])

    # View Report — open in new tab
    def _build_report_page(lang_val):
        with session.lock:
            report = session.last_report
        if not report:
            return dc(lang_val, "dc_no_report")
        return build_standalone_report(report, lang_val)

    view_btn.click(
        fn=_build_report_page,
        inputs=[lang_state],
        outputs=[hidden_report],
    ).then(
        fn=None,
        inputs=[hidden_report],
        js="""(html) => {
            if (!html || html.length < 50) { alert(html); return; }
            const w = window.open('', '_blank');
            if (w) { w.document.write(html); w.document.close(); }
        }""",
    )

    # E — Report persistence
    save_btn.click(fn=_save_report, inputs=[table_a, table_b, lang_state],
                   outputs=[save_status, load_dd])
    load_btn.click(fn=_list_reports, inputs=[], outputs=[load_dd])
    load_dd.change(fn=_load_report, inputs=[load_dd, lang_state], outputs=[result_html])

    # Home button
    home_btn.click(fn=None, js="() => { window.location.href = '/'; }")

    # Language switch — update all component labels/text
    def _switch_lang(choice, status_a_val, status_b_val):
        lg = "zh" if choice == "中文" else "en"
        t_fn = lambda k: dc(lg, k)

        def _status_update(current: str):
            # Translate the pristine "Not connected" placeholder; leave any
            # real connection status (it contains runtime info) untouched.
            pristine = {dc("en", "dc_not_connected"), dc("zh", "dc_not_connected")}
            if (current or "").strip() in pristine:
                return gr.update(label=t_fn("dc_status"),
                                 value=t_fn("dc_not_connected"))
            return gr.update(label=t_fn("dc_status"))

        return (
            lg,                                                         # lang_state
            t_fn("dc_title"),                                           # title_md
            f"**{t_fn('dc_source_a')}**",                               # src_a_md
            f"**{t_fn('dc_source_b')}**",                               # src_b_md
            gr.update(label=t_fn("dc_datasource_type")),                # ds_a
            gr.update(label=t_fn("dc_datasource_type")),                # ds_b
            gr.update(label=t_fn("dc_host")),                           # host_a
            gr.update(label=t_fn("dc_host")),                           # host_b
            gr.update(label=t_fn("dc_port")),                           # port_a
            gr.update(label=t_fn("dc_port")),                           # port_b
            gr.update(label=t_fn("dc_database")),                       # db_a
            gr.update(label=t_fn("dc_database")),                       # db_b
            gr.update(label=t_fn("dc_username")),                       # user_a
            gr.update(label=t_fn("dc_username")),                       # user_b
            gr.update(label=t_fn("dc_password")),                       # pwd_a
            gr.update(label=t_fn("dc_password")),                       # pwd_b
            gr.update(value=t_fn("dc_connect")),                        # conn_a
            gr.update(value=t_fn("dc_connect")),                        # conn_b
            _status_update(status_a_val),                               # status_a
            _status_update(status_b_val),                               # status_b
            gr.update(label=t_fn("dc_select_table")),                   # table_a
            gr.update(label=t_fn("dc_select_table")),                   # table_b
            gr.update(label=t_fn("dc_where_clause"),
                      placeholder=t_fn("dc_where_hint")),               # where_input
            gr.update(label=t_fn("dc_key_columns")),                    # key_input
            gr.update(value=t_fn("dc_compare_schema")),                 # schema_btn
            gr.update(value=t_fn("dc_compare_count")),                  # count_btn
            gr.update(value=t_fn("dc_compare_sample")),                 # sample_btn
            gr.update(value=t_fn("dc_compare_agg")),                    # agg_btn
            gr.update(value=t_fn("dc_compare_all")),                    # all_btn
            gr.update(value=t_fn("dc_batch_count")),                    # batch_btn
            gr.update(value=t_fn("dc_profile")),                        # profile_btn
            gr.update(label=t_fn("dc_custom_sql")),                     # sql_accordion
            gr.update(placeholder=t_fn("dc_sql_placeholder")),          # sql_a_input
            gr.update(placeholder=t_fn("dc_sql_placeholder")),          # sql_b_input
            gr.update(value=t_fn("dc_compare_sql")),                    # sql_btn
            gr.update(label=t_fn("dc_export_csv")),                     # csv_btn
            gr.update(label=t_fn("dc_export_excel")),                   # excel_btn
            gr.update(value=t_fn("dc_save_report")),                    # save_btn
            gr.update(label=t_fn("dc_load_report")),                    # load_dd
            gr.update(value=t_fn("dc_view_report")),                    # view_btn
            # Round 4 components
            gr.update(label=t_fn("dc_presets")),                        # presets_accordion
            gr.update(label=t_fn("dc_preset_name")),                    # preset_name_input
            gr.update(label=t_fn("dc_preset_env")),                     # preset_env_input
            gr.update(value=f'{t_fn("dc_preset_save")} (A)'),           # preset_save_btn
            gr.update(value=f'{t_fn("dc_preset_save")} (B)'),           # preset_save_b_btn
            gr.update(label=f"{t_fn('dc_preset_load')} (A)"),           # preset_dd_a
            gr.update(label=f"{t_fn('dc_preset_load')} (B)"),           # preset_dd_b
            gr.update(label=t_fn("dc_threshold"),
                      placeholder=t_fn("dc_threshold_hint")),           # threshold_input
            gr.update(label=t_fn("dc_col_mapping"),
                      placeholder=t_fn("dc_col_mapping_hint")),         # mapping_input
            gr.update(label=t_fn("dc_sample_strategy")),                # sample_strategy
            gr.update(value=t_fn("dc_batch_full")),                     # batch_full_btn
            gr.update(label=t_fn("dc_gen_sync")),                       # sync_accordion
            gr.update(value=t_fn("dc_gen_sync")),                       # gen_sync_btn
            gr.update(label=t_fn("dc_schedule")),                       # schedule_accordion
            gr.update(label=t_fn("dc_schedule_interval")),              # schedule_interval
            gr.update(value=t_fn("dc_schedule_start")),                 # schedule_start_btn
            gr.update(value=t_fn("dc_schedule_stop")),                  # schedule_stop_btn
            gr.update(label=t_fn("dc_trend")),                          # trend_accordion
            gr.update(label=t_fn("dc_alert_rules"),
                      placeholder=t_fn("dc_alert_rules_hint")),        # alert_rules_input
            gr.update(value=t_fn("dc_trend_chart")),                    # trend_btn
            # Round 5 components
            gr.update(label=t_fn("dc_masking_enabled")),                # masking_checkbox
            gr.update(value=t_fn("dc_reset_options")),                  # reset_options_btn
            gr.update(label=t_fn("dc_incremental")),                    # incremental_accordion
            gr.update(label=t_fn("dc_watermark_col"),
                      placeholder=t_fn("dc_watermark_hint")),           # watermark_col_input
            gr.update(label=t_fn("dc_watermark_value")),                # watermark_val_input
            gr.update(value=t_fn("dc_incremental_compare")),            # incremental_btn
            gr.update(label=t_fn("dc_quality")),                        # quality_accordion
            gr.update(label=t_fn("dc_quality_rules"),
                      placeholder=t_fn("dc_quality_rules_hint")),       # quality_rules_input
            gr.update(value=t_fn("dc_quality_check")),                  # quality_btn
            gr.update(value=t_fn("dc_gen_diff_sql")),                   # gen_diff_sql_btn
            gr.update(label=t_fn("dc_templates")),                      # templates_accordion
            gr.update(label=t_fn("dc_template_name")),                  # template_name_input
            gr.update(value=t_fn("dc_template_save")),                  # template_save_btn
            gr.update(label=t_fn("dc_template_load")),                  # template_dd
            gr.update(value=t_fn("dc_template_load")),                  # template_load_btn
            gr.update(label=t_fn("dc_webhook")),                        # webhook_accordion
            gr.update(label=t_fn("dc_webhook_url"),
                      placeholder=t_fn("dc_webhook_url_hint")),         # webhook_url_input
            gr.update(label=t_fn("dc_webhook_on_fail")),                # webhook_on_fail
            gr.update(label=t_fn("dc_environment")),                    # env_accordion
            gr.update(label=t_fn("dc_env_a"),
                      placeholder=t_fn("dc_env_hint")),                 # env_input_a
            gr.update(label=t_fn("dc_env_b"),
                      placeholder=t_fn("dc_env_hint")),                 # env_input_b
            gr.update(label=t_fn("dc_select_table")),                   # env_table_input
            gr.update(value=t_fn("dc_compare_envs")),                   # env_compare_btn
            # Round 6 — skew
            gr.update(label=t_fn("dc_skew")),                           # skew_accordion
            gr.update(label=t_fn("dc_skew_column"),
                      placeholder=t_fn("dc_skew_columns_hint")),        # skew_cols_input
            gr.update(value=t_fn("dc_skew_analyze")),                   # skew_btn
            # Round 7 — checksum, partition, custom agg
            gr.update(label=t_fn("dc_checksum")),                       # checksum_accordion
            gr.update(label=t_fn("dc_checksum"),
                      placeholder=t_fn("dc_checksum_columns_hint")),    # checksum_cols_input
            gr.update(value=t_fn("dc_checksum_analyze")),               # checksum_btn
            gr.update(value=t_fn("dc_chunked_btn")),                    # chunked_btn
            gr.update(label=t_fn("dc_partition")),                      # partition_accordion
            gr.update(label=t_fn("dc_partition_col"),
                      placeholder=t_fn("dc_partition_col_hint")),       # partition_col_input
            gr.update(value=t_fn("dc_partition_analyze")),              # partition_btn
            gr.update(label=t_fn("dc_custom_agg")),                    # custom_agg_accordion
            gr.update(label=t_fn("dc_custom_agg"),
                      placeholder=t_fn("dc_custom_agg_hint")),         # custom_agg_input
            gr.update(value=t_fn("dc_custom_agg_analyze")),            # custom_agg_btn
            # Round 8 — stratified sampling
            gr.update(label=t_fn("dc_stratified_col"),
                      placeholder=t_fn("dc_stratified_col_hint")),     # stratified_col_input
            # Round 9 — batch templates
            gr.update(label=t_fn("dc_batch_templates")),               # batch_template_dd
            gr.update(value=t_fn("dc_batch_templates_run")),           # batch_template_btn
            # Round 10 — report diff + lineage
            gr.update(label=t_fn("dc_report_old")),                    # report_old_dd
            gr.update(label=t_fn("dc_report_new")),                    # report_new_dd
            gr.update(value=t_fn("dc_report_compare")),                # report_diff_btn
            gr.update(label=t_fn("dc_lineage_title")),                 # lineage_accordion
            gr.update(label=t_fn("dc_lineage_hint")),                  # lineage_sql_input
            gr.update(value=t_fn("dc_lineage_title")),                 # lineage_btn
        )

    # Language follows the hub's choice (st-lang cookie), applied on load.
    # _switch_lang takes two extra inputs (status_a/b) — pass them through.
    if app is not None:
        from seatunnel_agent.common.lang_pref import STAMP_JS as _STAMP_JS
        from seatunnel_agent.common.lang_pref import choice_from_request as _choice
        app.load(fn=None, js=_STAMP_JS)
        # saved-report dropdown: choices are baked empty at build time —
        # populate on page load so the user never needs the ↻ button first
        app.load(fn=_list_reports, inputs=[], outputs=[load_dd])

        def _lang_on_load(a, b, request: gr.Request):
            return _switch_lang(_choice(request), a, b)

        app.load(
        fn=_lang_on_load,
        inputs=[status_a, status_b],
        outputs=[
            lang_state, title_md, src_a_md, src_b_md,
            ds_a, ds_b, host_a, host_b, port_a, port_b, db_a, db_b,
            user_a, user_b, pwd_a, pwd_b,
            conn_a, conn_b, status_a, status_b,
            table_a, table_b,
            where_input, key_input,
            schema_btn, count_btn, sample_btn, agg_btn,
            all_btn, batch_btn, profile_btn,
            sql_accordion, sql_a_input, sql_b_input, sql_btn,
            csv_btn, excel_btn, save_btn, load_dd, view_btn,
            # Round 4
            presets_accordion, preset_name_input, preset_env_input,
            preset_save_btn, preset_save_b_btn,
            preset_dd_a, preset_dd_b,
            threshold_input, mapping_input, sample_strategy,
            batch_full_btn,
            sync_accordion, gen_sync_btn,
            schedule_accordion, schedule_interval,
            schedule_start_btn, schedule_stop_btn,
            trend_accordion, alert_rules_input, trend_btn,
            # Round 5
            masking_checkbox, reset_options_btn,
            incremental_accordion, watermark_col_input, watermark_val_input, incremental_btn,
            quality_accordion, quality_rules_input, quality_btn,
            gen_diff_sql_btn,
            templates_accordion, template_name_input, template_save_btn,
            template_dd, template_load_btn,
            webhook_accordion, webhook_url_input, webhook_on_fail,
            env_accordion, env_input_a, env_input_b, env_table_input, env_compare_btn,
            # Round 6 — skew
            skew_accordion, skew_cols_input, skew_btn,
            # Round 7 — checksum, partition, custom agg
            checksum_accordion, checksum_cols_input, checksum_btn, chunked_btn,
            partition_accordion, partition_col_input, partition_btn,
            custom_agg_accordion, custom_agg_input, custom_agg_btn,
            # Round 8 — stratified sampling
            stratified_col_input,
            # Round 9 — batch templates
            batch_template_dd, batch_template_btn,
            # Round 10 — report diff + lineage
            report_old_dd, report_new_dd, report_diff_btn,
            lineage_accordion, lineage_sql_input, lineage_btn,
        ],
    )

    if app is not None:
        # Tab on an empty input fills in the gray placeholder (shared with text2sql)
        tab_fill_js = (Path(__file__).resolve().parent.parent / "text2sql"
                       / "resources" / "tab_fill.js").read_text(encoding="utf-8")
        app.load(fn=None, js=tab_fill_js)
