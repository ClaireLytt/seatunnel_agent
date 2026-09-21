"""Gradio page for the Text2SQL (Chat BI) agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Text2SQL", "/text2sql")``. Keeps its own holders/state so it is
fully independent from the SeaTunnel page.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import gradio as gr

from .config import Settings, load_settings
from .text2sql.executor import (
    DS_DEFAULTS,
    DS_TYPES,
    DIALECT_NAMES,
    DatabaseConfig,
    config_from_env,
    create_executor,
    schema_ddl_path_from_env,
)
from .text2sql.chat_history import (
    Text2SQLSession,
    delete_t2s_session,
    extract_title,
    list_t2s_sessions,
    load_t2s_session,
    new_session_id,
    now_iso,
    save_t2s_session,
)
from .text2sql.favorites import FavoritesStore
from .text2sql.templates import SQL_TEMPLATES, template_choices, template_description
from .text2sql.i18n import (
    HINTS_I18N,
    TOOL_EMOJI,
    TOOL_LABEL_I18N,
    t2s as _t2s,
)
from .text2sql.qlog import QueryLogger
from .text2sql.schema import SchemaStore



_shared_holder: dict[str, Any] = {}
_shared_holder_lock = threading.Lock()
_chart_cache: dict[str, str] = {}
_chart_cache_lock = threading.Lock()
_CHART_CACHE_MAX = 50


def _chart_cache_put(key: str, value: str) -> None:
    """Store a chart in the cache, evicting oldest entries if full."""
    with _chart_cache_lock:
        if len(_chart_cache) >= _CHART_CACHE_MAX:
            oldest = next(iter(_chart_cache))
            del _chart_cache[oldest]
        _chart_cache[key] = value


def _esc_html(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_schema_card(table, lang: str = "en", store=None) -> str:
    """Build an inline-styled HTML card for a TableSchema."""
    t = lambda k: _t2s(lang, k)
    esc = _esc_html

    type_colors = {"incremental": "#0ea5e9", "full": "#22c55e", "other": "#a3a3a3"}
    _type_i18n = {"incremental": "table_type_incremental", "full": "table_type_full"}
    tt = table.table_type
    type_color = type_colors.get(tt, "#a3a3a3")
    type_label = t(_type_i18n.get(tt, "table_type_other"))
    badges = (
        f'<span style="display:inline-block;padding:1px 6px;border-radius:3px;'
        f'font-size:10px;color:#fff;background:{type_color};margin-left:6px;">'
        f'{t("schema_table_type")} {esc(type_label)}</span>'
    )
    if table.is_partitioned:
        badges += (
            '<span style="display:inline-block;padding:1px 6px;border-radius:3px;'
            'font-size:10px;color:#fff;background:#f59e0b;margin-left:4px;">partitioned</span>'
        )

    col_count = len(table.columns) + len(table.partition_columns)
    header = (
        f'<div style="font-weight:600;font-size:13px;margin-bottom:2px;">'
        f'{esc(table.full_name)}{badges}</div>'
    )
    comment = ""
    if table.comment:
        comment = f'<div style="color:#888;font-size:11px;margin-bottom:6px;">{esc(table.comment)}</div>'
    summary = (
        f'<div style="font-size:11px;color:#666;margin-bottom:4px;">'
        f'{t("schema_col_count").format(n=col_count)}</div>'
    )

    th_style = 'style="text-align:left;padding:2px 4px;border-bottom:1px solid #e5e7eb;font-size:11px;background:#f9fafb;"'
    td_style = 'style="padding:2px 4px;border-bottom:1px solid #f3f4f6;font-size:11px;"'
    rows_html = ""
    for col in table.columns:
        rows_html += (
            f"<tr><td {td_style}>{esc(col.name)}</td>"
            f'<td {td_style}><code style="font-size:10px;color:#0ea5e9;">{esc(col.dtype)}</code></td>'
            f"<td {td_style}>{esc(col.comment)}</td></tr>"
        )
    col_table = (
        f'<div style="margin-bottom:4px;font-weight:500;font-size:11px;">{t("schema_columns")}</div>'
        f'<table style="width:100%;border-collapse:collapse;">'
        f"<tr><th {th_style}>Name</th><th {th_style}>Type</th><th {th_style}>Comment</th></tr>"
        f"{rows_html}</table>"
    )

    part_html = ""
    if table.partition_columns:
        p_rows = ""
        for col in table.partition_columns:
            p_rows += (
                f"<tr><td {td_style}><b>{esc(col.name)}</b></td>"
                f'<td {td_style}><code style="font-size:10px;color:#f59e0b;">{esc(col.dtype)}</code></td>'
                f"<td {td_style}>{esc(col.comment)}</td></tr>"
            )
        part_html = (
            f'<div style="margin-top:8px;margin-bottom:4px;font-weight:500;font-size:11px;">'
            f'{t("schema_partition_cols")}</div>'
            f'<table style="width:100%;border-collapse:collapse;">'
            f"<tr><th {th_style}>Name</th><th {th_style}>Type</th><th {th_style}>Comment</th></tr>"
            f"{p_rows}</table>"
        )

    join_html = ""
    if store is not None:
        from .text2sql.join_advisor import suggest_joins
        suggestions = suggest_joins(table.full_name, store)
        if suggestions:
            join_rows = ""
            for s in suggestions:
                type_label = t("join_exact") if s.match_type == "exact_name" else t("join_fk")
                join_rows += (
                    f"<tr><td {td_style}><code>{esc(s.table_b)}</code></td>"
                    f"<td {td_style}>{esc(s.column_a)} = {esc(s.column_b)}</td>"
                    f'<td {td_style}><span style="font-size:10px;color:#6b7280;">'
                    f'{esc(type_label)} ({s.confidence:.0%})</span></td></tr>'
                )
            join_html = (
                f'<details style="margin-top:8px;">'
                f'<summary style="cursor:pointer;font-weight:500;font-size:11px;color:#1e40af;">'
                f'\U0001f517 {t("join_suggestions")} ({len(suggestions)})</summary>'
                f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
                f'<tr><th {th_style}>Table</th><th {th_style}>Condition</th><th {th_style}>Type</th></tr>'
                f'{join_rows}</table></details>'
            )

    return (
        f'<div style="font-size:12px;line-height:1.5;padding:4px;max-height:400px;overflow-y:auto;">'
        f"{header}{comment}{summary}{col_table}{part_html}{join_html}</div>"
    )


def build_lineage_card(lineage, lang: str = "en") -> str:
    """Build an inline-styled HTML card for an SqlLineage."""
    from .text2sql.lineage import SqlLineage
    t = lambda k: _t2s(lang, k)
    esc = _esc_html

    if not lineage.source_tables and not lineage.output_columns:
        return ""

    parts: list[str] = []
    sec_style = 'style="font-weight:600;font-size:11px;margin:6px 0 3px 0;color:#374151;"'
    td_style = 'style="padding:2px 6px;font-size:11px;border-bottom:1px solid #f3f4f6;"'
    badge = lambda text, color: (
        f'<span style="display:inline-block;padding:0 5px;border-radius:3px;'
        f'font-size:9px;color:#fff;background:{color};margin-left:4px;">{esc(text)}</span>'
    )

    # Source tables
    if lineage.source_tables:
        parts.append(f'<div {sec_style}>{t("lineage_sources")}</div>')
        for tbl in lineage.source_tables:
            used = sum(1 for c in lineage.output_columns
                       if c.source_table == tbl)
            count_text = t("lineage_cols_used").format(n=used) if used else ""
            parts.append(
                f'<div style="font-size:11px;padding:1px 0 1px 8px;">'
                f'\U0001f4e6 <b>{esc(tbl)}</b>'
                f'<span style="color:#888;margin-left:6px;">{esc(count_text)}</span></div>'
            )

    # Output columns
    if lineage.output_columns:
        parts.append(f'<div {sec_style}>{t("lineage_outputs")}</div>')
        parts.append('<table style="width:100%;border-collapse:collapse;">')
        for col in lineage.output_columns:
            source = ""
            if col.source_table and col.source_column:
                source = f"{col.source_table}.{col.source_column}"
            elif col.expression and col.expression != col.output_name:
                source = col.expression
            badges = ""
            if col.is_aggregation:
                badges = badge(t("lineage_aggregation"), "#8b5cf6")
            elif not col.source_table and col.output_name != "*":
                badges = badge(t("lineage_computed"), "#6b7280")
            parts.append(
                f'<tr><td {td_style}><b>{esc(col.output_name)}</b></td>'
                f'<td style="padding:2px 6px;font-size:11px;border-bottom:1px solid #f3f4f6;color:#666;">'
                f'← {esc(source)}{badges}</td></tr>'
            )
        parts.append("</table>")

    # Joins
    if lineage.joins:
        parts.append(f'<div {sec_style}>{t("lineage_joins")}</div>')
        for j in lineage.joins:
            parts.append(
                f'<div style="font-size:11px;padding:1px 0 1px 8px;color:#0369a1;">'
                f'\U0001f517 {esc(j)}</div>'
            )

    # Filters
    if lineage.filters:
        parts.append(f'<div {sec_style}>{t("lineage_filters")}</div>')
        for f_item in lineage.filters:
            parts.append(
                f'<div style="font-size:11px;padding:1px 0 1px 8px;color:#92400e;">'
                f'\U0001f50d {esc(f_item)}</div>'
            )

    # Group By
    if lineage.group_by:
        parts.append(f'<div {sec_style}>{t("lineage_group_by")}</div>')
        parts.append(
            f'<div style="font-size:11px;padding:1px 0 1px 8px;color:#4338ca;">'
            f'{esc(", ".join(lineage.group_by))}</div>'
        )

    body = "\n".join(parts)
    return (
        f'<details style="margin-top:6px;">'
        f'<summary style="cursor:pointer;font-weight:600;font-size:12px;color:#1e40af;">'
        f'\U0001f9ec {t("lineage_title")}</summary>'
        f'<div style="font-size:12px;line-height:1.5;padding:4px;margin-top:4px;'
        f'border:1px solid #e5e7eb;border-radius:6px;">{body}</div></details>'
    )


def build_quality_card(warnings: list[dict], lang: str = "en") -> str:
    """Build an inline-styled HTML card for data quality warnings."""
    t = lambda k: _t2s(lang, k)
    esc = _esc_html
    if not warnings:
        return ""

    type_labels = {
        "high_null": t("quality_high_null"),
        "constant": t("quality_constant"),
        "outlier": t("quality_outlier"),
        "duplicate_rows": t("quality_duplicate_rows"),
    }
    type_colors = {
        "high_null": "#f59e0b",
        "constant": "#6b7280",
        "outlier": "#ef4444",
        "duplicate_rows": "#8b5cf6",
    }

    items: list[str] = []
    for w in warnings:
        wtype = w.get("warning_type", "")
        label = type_labels.get(wtype, wtype)
        color = type_colors.get(wtype, "#6b7280")
        col = w.get("column", "")
        detail = w.get("detail", "")
        col_part = f"<b>{esc(col)}</b> — " if col else ""
        items.append(
            f'<div style="font-size:11px;padding:2px 0;">'
            f'<span style="display:inline-block;padding:0 5px;border-radius:3px;'
            f'font-size:9px;color:#fff;background:{color};margin-right:4px;">{esc(label)}</span>'
            f'{col_part}{esc(detail)}</div>'
        )

    body = "\n".join(items)
    return (
        f'<details style="margin-top:6px;">'
        f'<summary style="cursor:pointer;font-weight:600;font-size:12px;color:#f59e0b;">'
        f'⚠️ {t("quality_title")} — {t("quality_warnings").format(n=len(warnings))}</summary>'
        f'<div style="font-size:12px;line-height:1.5;padding:4px;margin-top:4px;'
        f'border:1px solid #fde68a;border-radius:6px;background:#fffbeb;">{body}</div></details>'
    )


def build_diff_card(diff_data: dict, lang: str = "en") -> str:
    """Build an inline-styled HTML card for result diff."""
    t = lambda k: _t2s(lang, k)
    items: list[str] = []
    added = diff_data.get("added_count", 0)
    removed = diff_data.get("removed_count", 0)
    if added:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#16a34a;">'
            f'<b>+{added}</b> {t("diff_added_rows")}</div>'
        )
    if removed:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#dc2626;">'
            f'<b>-{removed}</b> {t("diff_removed_rows")}</div>'
        )
    cols_added = diff_data.get("cols_added", [])
    cols_removed = diff_data.get("cols_removed", [])
    if cols_added:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#16a34a;">'
            f'{t("diff_cols_added")}: {_esc_html(", ".join(cols_added))}</div>'
        )
    if cols_removed:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#dc2626;">'
            f'{t("diff_cols_removed")}: {_esc_html(", ".join(cols_removed))}</div>'
        )
    old_c = diff_data.get("old_count", 0)
    new_c = diff_data.get("new_count", 0)
    if old_c != new_c:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#6b7280;">'
            f'{old_c} → {new_c} rows</div>'
        )

    body = "\n".join(items)
    return (
        f'<details style="margin-top:6px;">'
        f'<summary style="cursor:pointer;font-weight:600;font-size:12px;color:#0369a1;">'
        f'\U0001f504 {t("diff_title")}</summary>'
        f'<div style="font-size:12px;line-height:1.5;padding:4px;margin-top:4px;'
        f'border:1px solid #bae6fd;border-radius:6px;background:#f0f9ff;">{body}</div></details>'
    )


def build_profile_card(profile, lang: str = "en") -> str:
    """Build an inline-styled HTML card for a TableProfile."""
    t = lambda k: _t2s(lang, k)
    esc = _esc_html

    th_style = 'style="text-align:left;padding:2px 4px;border-bottom:1px solid #e5e7eb;font-size:10px;background:#f9fafb;"'
    td_style = 'style="padding:2px 4px;border-bottom:1px solid #f3f4f6;font-size:11px;"'

    rows_html = ""
    for cp in profile.columns:
        null_pct = f"{cp.null_count / cp.total_count:.0%}" if cp.total_count else "—"
        rows_html += (
            f"<tr><td {td_style}><b>{esc(cp.name)}</b></td>"
            f'<td {td_style}><code style="font-size:10px;">{esc(cp.dtype)}</code></td>'
            f"<td {td_style}>{cp.distinct_count}</td>"
            f"<td {td_style}>{null_pct}</td>"
            f"<td {td_style}>{esc(str(cp.min_value)) if cp.min_value is not None else '—'}</td>"
            f"<td {td_style}>{esc(str(cp.max_value)) if cp.max_value is not None else '—'}</td></tr>"
        )

    return (
        f'<details style="margin-top:6px;" open>'
        f'<summary style="cursor:pointer;font-weight:600;font-size:12px;color:#7c3aed;">'
        f'\U0001f4ca {t("profile_title")} — {esc(profile.table_name)} '
        f'({t("profile_total_rows")}: {profile.row_count})</summary>'
        f'<div style="padding:4px;margin-top:4px;border:1px solid #e5e7eb;border-radius:6px;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<tr><th {th_style}>Column</th><th {th_style}>Type</th>'
        f'<th {th_style}>{t("profile_distinct")}</th>'
        f'<th {th_style}>NULL%</th>'
        f'<th {th_style}>{t("profile_min")}</th>'
        f'<th {th_style}>{t("profile_max")}</th></tr>'
        f'{rows_html}</table></div></details>'
    )


def _md_table(columns: list[str], rows: list[list[Any]], max_rows: int = 20, lang: str = "en") -> str:
    if not columns:
        return _t2s(lang, "no_result")
    header = "| " + " | ".join(
        str(c).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for c in columns
    ) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    lines = [header, sep]
    for r in rows[:max_rows]:
        cells = [str(v) if v is not None else "" for v in r]
        lines.append("| " + " | ".join(
            c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")
            for c in cells
        ) + " |")
    return "\n".join(lines)



def _format_tool_result(name: str, raw: str, lang: str = "en",
                        store: SchemaStore | None = None) -> str:
    from .text2sql.formatter import format_sql
    from .text2sql.lineage import trace_lineage

    t = lambda k: _t2s(lang, k)
    labels = TOOL_LABEL_I18N.get(lang, TOOL_LABEL_I18N["en"])
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"\U0001f4e6 **{name}**\n```\n{str(raw)[:500]}\n```"

    label = labels.get(name, name)

    if data.get("error"):
        return f"❌ **{label} {t('failed')}**\n\n{str(data['error'])[:500]}"

    if name == "match_tables":
        lines = [f"\U0001f50d **{t('candidates')}** ({data.get('count', 0)}):", ""]
        for c in data.get("candidates", []):
            cols = ", ".join(c.get("matched_columns", [])[:5])
            lines.append(
                f"- **`{c['table']}`** — {c.get('comment', '')} "
                f"({t('score')} {c.get('score', 0)}, {t('type')} {c.get('table_type', '?')})"
                + (f", {t('matched_cols')}: {cols}" if cols else "")
            )
        return "\n".join(lines)

    if name == "get_table_schema":
        cols = data.get("columns", [])
        parts = [
            f"\U0001f4d6 **`{data.get('table', '?')}`** — {data.get('comment', '')}",
            f"{t('table_type')}: {data.get('table_type', '?')} · {t('cols_count')}: {len(cols)}"
            + (f" · {t('partitioned')}" if data.get("partitioned") else ""),
        ]
        if data.get("partition_columns"):
            pc = ", ".join(
                f"`{p['name']}`({p.get('comment', '')})"
                for p in data["partition_columns"]
            )
            parts.append(f"Partition: {pc}")
        return "\n\n".join(parts)

    if name == "get_max_partition":
        return (
            f"\U0001f4c5 **{t('max_partition')}** `{data.get('table', '?')}` → "
            f"`{data.get('partition_column', 'pt')}={data.get('max_partition', '?')}`"
        )

    if name == "explain_sql":
        sql = data.get("sql", "")
        plan = data.get("plan", "")
        return (
            f"\U0001f4cb **{t('explain_result')}**\n\n"
            f"```sql\n{sql}\n```\n\n"
            f"```\n{plan}\n```"
        )

    if name == "execute_sql":
        sql = data.get("sql", "")
        display_sql = format_sql(sql) if sql else sql
        if data.get("cached"):
            header = f"⚡ **{t('exec_success')}** — {t('cache_hit').format(rows=data.get('row_count', 0))}"
        else:
            header = f"⚡ **{t('exec_success')}**"
        lines = [
            header,
            "",
            f"```sql\n{display_sql}\n```",
            f"⏱ {t('elapsed')} **{data.get('elapsed_ms', '?')} ms** · "
            f"**{data.get('row_count', 0)}** {t('rows')}"
            + (f" {t('truncated')}" if data.get("truncated") else ""),
            "",
            _md_table(data.get("columns", []), data.get("preview_rows", []), lang=lang),
        ]
        if sql:
            try:
                lineage = trace_lineage(sql, store)
                card = build_lineage_card(lineage, lang)
                if card:
                    lines.append("")
                    lines.append(card)
            except Exception:
                pass
        quality_warnings = data.get("quality_warnings")
        if quality_warnings:
            card = build_quality_card(quality_warnings, lang)
            if card:
                lines.append("")
                lines.append(card)
        diff_data = data.get("diff")
        if diff_data:
            card = build_diff_card(diff_data, lang)
            if card:
                lines.append("")
                lines.append(card)
        return "\n".join(lines)

    if name == "export_csv":
        return (
            f"\U0001f4be **{t('csv_exported')}** ({data.get('row_count', 0)} {t('rows')})\n\n"
            f"`{data.get('csv_path', '?')}`"
        )

    if name == "export_excel":
        return (
            f"\U0001f4ca **{t('excel_exported')}** ({data.get('row_count', 0)} {t('rows')})\n\n"
            f"`{data.get('excel_path', '?')}`"
        )

    if name == "export_pdf":
        return (
            f"\U0001f4c4 **{t('pdf_exported')}** ({data.get('row_count', 0)} {t('rows')})\n\n"
            f"`{data.get('pdf_path', '?')}`"
        )

    if name == "get_result_page":
        page = data.get("page", 1)
        total_pages = data.get("total_pages", 1)
        header = f"\U0001f4c3 **{t('page_label').format(page=page, total=total_pages)}** — {t('page_info').format(total=data.get('total_rows', 0))}"
        table = _md_table(data.get("columns", []), data.get("rows", []), max_rows=200, lang=lang)
        return f"{header}\n\n{table}"

    return f"\U0001f4e6 **{label}**\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:600]}\n```"


class _IncrementalFormatter:
    """Formats events incrementally — only processes new events on each call.

    Delta handling: text_delta events accumulate in a buffer. A temporary
    cursor message is appended at the END of each ``feed()`` call and removed
    at the START of the next one.  The ``text`` event (complete text) simply
    discards the buffer; non-text events flush it as a permanent message.
    """

    def __init__(self, start_time: float | None, lang: str, store: SchemaStore | None):
        self._start = start_time
        self._lang = lang
        self._store = store
        self._t = lambda k: _t2s(lang, k)
        self._labels = TOOL_LABEL_I18N.get(lang, TOOL_LABEL_I18N["en"])
        self.messages: list[dict[str, str]] = []
        self._delta_buf: list[str] = []
        self._has_cursor = False
        self._delta_flush_idx: int | None = None

    def _remove_cursor(self) -> None:
        if self._has_cursor and self.messages:
            self.messages.pop()
            self._has_cursor = False

    def feed(self, new_events: list[dict[str, Any]]) -> list[dict[str, str]]:
        self._remove_cursor()

        t = self._t
        labels = self._labels
        for ev in new_events:
            tp = ev["type"]
            if tp == "text_delta":
                self._delta_buf.append(ev.get("text", ""))
                continue
            if tp == "text":
                self._delta_buf.clear()
            elif self._delta_buf:
                acc = "".join(self._delta_buf)
                if acc.strip():
                    self._delta_flush_idx = len(self.messages)
                    self.messages.append({"role": "assistant", "content": acc})
                self._delta_buf.clear()

            if tp == "step":
                phase = ev.get("phase", "")
                phase_label = {"thinking": t("generating"), "executing_tools": t("executing")}.get(phase, phase)
                elapsed = f" ({time.time() - self._start:.1f}s)" if self._start else ""
                self.messages.append({
                    "role": "assistant",
                    "content": f"⏳ **Step {ev.get('iteration', '?')}** — {phase_label}{elapsed}",
                })
            elif tp == "thinking":
                text = ev.get("text", "")
                if text:
                    preview = text[:600] + ("..." if len(text) > 600 else "")
                    self.messages.append({"role": "assistant", "content": f"\U0001f4ad **{t('thinking')}**\n\n{preview}"})
            elif tp == "text":
                full = ev.get("text")
                if full:
                    if self._delta_flush_idx is not None:
                        self.messages[self._delta_flush_idx] = {"role": "assistant", "content": full}
                    else:
                        self.messages.append({"role": "assistant", "content": full})
                self._delta_flush_idx = None
            elif tp == "tool_call":
                name = ev.get("name", "?")
                emoji = TOOL_EMOJI.get(name, "\U0001f527")
                label = labels.get(name, name)
                inp = ev.get("input", {})
                if name == "execute_sql" and inp.get("sql"):
                    body = f"```sql\n{inp['sql']}\n```"
                else:
                    args = ", ".join(f"{k}={repr(v)[:100]}" for k, v in inp.items())
                    body = f"`{args}`" if args else ""
                self.messages.append({"role": "assistant", "content": f"{emoji} **{label}**\n{body}"})
            elif tp == "tool_result":
                self.messages.append({
                    "role": "assistant",
                    "content": _format_tool_result(
                        ev.get("name", "?"), ev.get("result", "{}"),
                        self._lang, store=self._store,
                    ),
                })
            elif tp == "usage":
                inp_t, out_t = ev.get("input_tokens", 0), ev.get("output_tokens", 0)
                if inp_t or out_t:
                    self.messages.append({"role": "assistant", "content": f"📊 Tokens: {inp_t:,} in / {out_t:,} out"})
            elif tp == "sql_retry":
                attempt = ev.get("attempt", 0)
                max_r = ev.get("max", 3)
                etype = ev.get("error_type", "execution_error")
                etype_label = t(f"error_type_{etype}") if t(f"error_type_{etype}") != f"error_type_{etype}" else etype
                hint = ev.get("retry_hint", "")
                header = t("sql_retry").format(attempt=attempt, max=max_r)
                detail = t("sql_retry_hint").format(error_type=etype_label, hint=hint)
                failed_sql = ev.get("failed_sql", "")
                parts = [f"{header}\n\n{detail}"]
                if failed_sql:
                    parts.append(f"\n```sql\n{failed_sql}\n```")
                self.messages.append({"role": "assistant", "content": "".join(parts)})

        if self._delta_buf:
            acc = "".join(self._delta_buf)
            if acc.strip():
                self.messages.append({"role": "assistant", "content": acc + " ▌"})
                self._has_cursor = True

        return self.messages

    def finalize(self) -> list[dict[str, str]]:
        self._remove_cursor()
        if self._delta_buf:
            acc = "".join(self._delta_buf)
            if acc.strip():
                self.messages.append({"role": "assistant", "content": acc})
        self._delta_buf.clear()
        self._delta_flush_idx = None
        return self.messages


def _format_events(events: list[dict[str, Any]], start_time: float | None = None,
                    lang: str = "en", store: SchemaStore | None = None) -> list[dict[str, str]]:
    fmt = _IncrementalFormatter(start_time, lang, store)
    fmt.feed(events)
    return fmt.finalize()


def _history_rows(logger: QueryLogger, n: int = 100) -> list[list[str]]:
    rows = []
    for i, rec in enumerate(reversed(logger.recent(n))):
        status = rec.get("status", "")
        badge = "✅" if status == "success" else "❌" if status == "error" else "⏳"
        sql_full = rec.get("generated_sql") or ""
        if sql_full and status == "success":
            sql_hash = hashlib.md5(sql_full.encode()).hexdigest()
            with _chart_cache_lock:
                has_chart = sql_hash in _chart_cache
            if has_chart:
                badge += "📊"
        elapsed = rec.get("exec_time_ms")
        elapsed_str = f"{elapsed}ms" if elapsed is not None else ""
        ts = rec.get("timestamp", "")
        if "T" in ts:
            ts = ts.replace("T", " ")
        sql = sql_full
        if len(sql) > 120:
            sql = sql[:120] + "..."
        rows.append([
            str(i),
            ts,
            rec.get("user_query", ""),
            f"{badge}",
            elapsed_str,
            sql,
        ])
    return rows


def render_schema_browser_page(app=None) -> None:
    """Standalone schema browser page opened in a new tab."""
    lang = "en"
    t = lambda k: _t2s(lang, k)

    def _table_choices_from_shared(lang):
        with _shared_holder_lock:
            store = _shared_holder.get("full_store")
        if not store:
            return []
        choices = []
        for tb in store.tables:
            if lang == "zh" and tb.comment:
                label = f"{tb.name} ({tb.comment})"
            else:
                label = tb.name
            choices.append(label)
        return choices

    def _browse(table_choice, lang):
        if not table_choice:
            return ""
        name = table_choice.split("(")[0].strip()
        with _shared_holder_lock:
            store = _shared_holder.get("full_store")
        if not store:
            return ""
        table = store.get(name)
        if table is None:
            for tb in store.tables:
                if tb.name == name:
                    table = tb
                    break
        if table is None:
            return ""
        return build_schema_card(table, lang, store=store)

    def _refresh(lang):
        choices = _table_choices_from_shared(lang)
        return gr.update(choices=choices, value=None), ""

    def _switch_lang(choice):
        lang = "zh" if choice == "中文" else "en"
        t = lambda k: _t2s(lang, k)
        choices = _table_choices_from_shared(lang)
        return (
            lang,
            gr.update(value=f"## {t('schema_browser')}"),
            gr.update(value=t("schema_back")),
            gr.update(value=t("refresh")),
            gr.update(choices=choices, value=None),
            "",
        )

    with gr.Column():
        lang_state = gr.State("en")
        with gr.Row(elem_classes=["st-topbar-row"]):
            gr.HTML('<div class="st-topbar-spacer"></div>')
            lang_dd = gr.Dropdown(
                choices=["English", "中文"], value="English",
                show_label=False, container=False, min_width=140,
                elem_classes=["st-lang-dd"],
            )

        title_md = gr.Markdown(f"## {t('schema_browser')}")

        with gr.Row():
            back_btn = gr.Button(t("schema_back"), variant="secondary", size="sm")
            refresh_btn = gr.Button(t("refresh"), variant="secondary", size="sm")

        with _shared_holder_lock:
            _has_store = _shared_holder.get("full_store") is not None
        no_tables_msg = t("schema_no_tables") if not _has_store else ""
        schema_dd = gr.Dropdown(
            choices=_table_choices_from_shared("en"),
            value=None, label="",
            show_label=False,
        )
        schema_html = gr.HTML(no_tables_msg)

    schema_dd.change(fn=_browse, inputs=[schema_dd, lang_state], outputs=[schema_html])
    refresh_btn.click(fn=_refresh, inputs=[lang_state], outputs=[schema_dd, schema_html])
    back_btn.click(fn=None, js="() => { window.close(); }")
    lang_dd.change(
        fn=_switch_lang, inputs=[lang_dd],
        outputs=[lang_state, title_md, back_btn, refresh_btn, schema_dd, schema_html],
    )

    def _on_load():
        choices = _table_choices_from_shared("en")
        msg = "" if choices else _t2s("en", "schema_no_tables")
        return gr.update(choices=choices, value=None), msg

    if app is not None:
        app.load(fn=_on_load, outputs=[schema_dd, schema_html])


def _session_choices_global() -> list[str]:
    sessions = list_t2s_sessions()
    return [f"{s['title']} ({s['updated_at'][:10]}) [{s['id']}]" for s in sessions]



def render_history_page(app=None) -> None:
    """Full-page query history viewer."""
    logger = QueryLogger()
    fav_store = FavoritesStore()

    _HIST_ROW_HL_JS = """
    () => {
      requestAnimationFrame(() => {
        document.querySelectorAll('.st-hist-table table tbody tr').forEach(tr => {
          if (tr.dataset._hlBound) return;
          tr.dataset._hlBound = '1';
          tr.style.cursor = 'pointer';
          tr.addEventListener('click', () => {
            const wasSelected = tr.classList.contains('st-row-selected');
            const idx = Array.from(tr.parentNode.children).indexOf(tr);
            document.querySelectorAll('.st-hist-table table tbody tr').forEach(r => {
              r.classList.remove('st-row-selected');
            });
            const tb = document.querySelector('#hist-sel-idx textarea, #hist-sel-idx input');
            if (wasSelected) {
              if (tb) { tb.value = '-1'; tb.dispatchEvent(new Event('input', {bubbles:true})); }
            } else {
              tr.classList.add('st-row-selected');
              if (tb) { tb.value = String(idx); tb.dispatchEvent(new Event('input', {bubbles:true})); }
            }
          });
        });
      });
    }
    """

    with gr.Column(elem_classes=["st-history-page"]):
        lang_state = gr.State("en")
        with gr.Row(elem_classes=["st-topbar-row"]):
            gr.HTML('<div class="st-topbar-spacer"></div>')
            lang_dd = gr.Dropdown(
                choices=["English", "中文"],
                value="English",
                show_label=False,
                container=False,
                min_width=140,
                elem_classes=["st-lang-dd"],
            )

        title_md = gr.Markdown("## Query History")

        gr.Markdown("### 💬 Sessions")
        _sess_choices = _session_choices_global()
        session_dd = gr.Dropdown(
            choices=_sess_choices,
            value=None,
            label="",
            show_label=False,
            elem_classes=["st-sidebar-control"],
        )
        with gr.Row(elem_classes=["st-hist-toolbar"]):
            resume_btn = gr.Button("💬 Resume Chat", variant="primary", size="sm",
                                    elem_classes=["st-hist-btn"])

        gr.Markdown("### 📋 Query Log")

        with gr.Row(elem_classes=["st-hist-toolbar"]):
            back_btn = gr.Button("← Back", variant="secondary", size="sm",
                                 elem_classes=["st-hist-btn"])
            refresh_btn = gr.Button("↻ Refresh", variant="secondary", size="sm",
                                    elem_classes=["st-hist-btn"])
            save_fav_btn = gr.Button("⭐ Save to Favorites", variant="secondary", size="sm",
                                     elem_classes=["st-hist-btn"])
            export_sel_btn = gr.DownloadButton("📥 Export Selected", variant="secondary", size="sm",
                                                elem_classes=["st-hist-btn"])
            export_all_btn = gr.DownloadButton("📥 Export All CSV", variant="secondary", size="sm",
                                                elem_classes=["st-hist-btn"])
            delete_btn = gr.Button("✕ Delete Selected", variant="stop", size="sm",
                                   elem_classes=["st-hist-btn"])
            clear_btn = gr.Button("Clear All", variant="stop", size="sm",
                                  elem_classes=["st-hist-btn"])

        selected_state = gr.State([])
        selected_info = gr.Markdown("", elem_classes=["st-hist-sel-info"])
        selected_idx_box = gr.Textbox(visible=False, elem_id="hist-sel-idx")

        history_table = gr.Dataframe(
            headers=["#", "Time", "Question", "", "Elapsed", "SQL"],
            value=_history_rows(logger),
            interactive=False,
            wrap=True,
            column_widths=["36px", "140px", "32%", "32px", "60px", "38%"],
            elem_classes=["st-hist-table"],
        )

        detail_html = gr.HTML("", elem_classes=["st-hist-detail"])

        gr.HTML(
            '<style>'
            '.st-hist-table table tbody tr.st-row-selected,'
            '.st-fav-table table tbody tr.st-row-selected'
            ' { background: var(--color-accent-soft, #dbeafe) !important; }'
            '@media (prefers-color-scheme: dark) {'
            '  .st-hist-table table tbody tr.st-row-selected,'
            '  .st-fav-table table tbody tr.st-row-selected'
            '  { background: #1e3a5f !important; }'
            '}'
            '.st-hist-detail { padding: 0 8px; }'
            '</style>'
        )

    def _build_detail(row: int) -> str:
        records = list(reversed(logger.recent(100)))
        if row < 0 or row >= len(records):
            return ""
        rec = records[row]
        question = _esc_html(rec.get("user_query", ""))
        sql = _esc_html(rec.get("generated_sql", ""))
        ts = _esc_html(rec.get("timestamp", "").replace("T", " "))
        status = rec.get("status", "")
        elapsed = rec.get("exec_time_ms")
        badge = "✅" if status == "success" else "❌" if status == "error" else "⏳"
        elapsed_str = f"{elapsed}ms" if elapsed is not None else ""
        html = (
            f'<div style="border:1px solid var(--border-color-primary, #e5e7eb);'
            f'border-radius:8px;padding:12px;margin:8px 0;'
            f'background:var(--background-fill-secondary, #f9fafb);font-size:13px;">'
            f'<div style="margin-bottom:8px;"><b>Row #{row}</b> &nbsp; {badge} &nbsp; '
            f'<span style="color:var(--body-text-color-subdued, #6b7280);">{ts}</span> &nbsp; '
            f'<span style="color:var(--body-text-color-subdued, #6b7280);">{elapsed_str}</span></div>'
            f'<div style="margin-bottom:6px;"><b>Question:</b> {question}</div>'
            f'<div><b>SQL:</b></div>'
            f'<pre style="background:#1e293b;color:#e2e8f0;padding:10px;border-radius:6px;'
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;font-size:12px;">'
            f'{sql}</pre>'
            f'</div>'
        )
        return html

    def _on_select(evt: gr.SelectData, current: list):
        row = evt.index[0]
        if current == [row]:
            return [], "", ""
        question = ""
        records = list(reversed(logger.recent(100)))
        if 0 <= row < len(records):
            question = records[row].get("user_query", "")
            if len(question) > 60:
                question = question[:60] + "..."
        info = f"**Selected row #{row}:** {question}"
        return [row], info, _build_detail(row)

    def _on_js_select(idx_str: str):
        try:
            row = int(idx_str)
        except (ValueError, TypeError):
            return [], "", ""
        if row < 0:
            return [], "", ""
        records = list(reversed(logger.recent(100)))
        question = ""
        if 0 <= row < len(records):
            question = records[row].get("user_query", "")
            if len(question) > 60:
                question = question[:60] + "..."
        info = f"**Selected row #{row}:** {question}"
        return [row], info, _build_detail(row)

    def _refresh():
        return _history_rows(logger), [], "", ""

    def _delete_selected(selected: list):
        if selected:
            logger.delete(selected)
        return _history_rows(logger), [], "", ""

    def _clear():
        logger.clear()
        return [], [], "", ""

    def _save_to_favorites(selected: list, lang: str):
        if not selected:
            gr.Warning(_t2s(lang, "hist_no_selection"))
            return
        records = list(reversed(logger.recent(100)))
        saved = 0
        for idx in selected:
            if 0 <= idx < len(records):
                rec = records[idx]
                sql = rec.get("generated_sql", "")
                question = rec.get("user_query", "")
                if sql:
                    name = question[:60] if question else sql[:40]
                    fav_store.save(name=name, sql=sql, question=question, ds_type="")
                    saved += 1
        if saved:
            gr.Info(_t2s(lang, "hist_favorite_saved").format(name=f"{saved}"))

    def _export_selected(selected: list, lang: str):
        if not selected:
            raise gr.Error(_t2s(lang, "hist_no_selection"))
        records = list(reversed(logger.recent(100)))
        records = [records[i] for i in selected if 0 <= i < len(records)]
        if not records:
            raise gr.Error(_t2s(lang, "hist_no_selection"))
        import tempfile
        from .text2sql.exporter import export_csv
        out_dir = Path(tempfile.gettempdir()) / "text2sql_exports"
        out_dir.mkdir(exist_ok=True)
        columns = ["Time", "Question", "Status", "Elapsed(ms)", "SQL"]
        rows = [(r.get("timestamp", ""), r.get("user_query", ""),
                 r.get("status", ""), r.get("exec_time_ms", ""),
                 r.get("generated_sql", "")) for r in records]
        return export_csv(columns=columns, rows=rows, path=str(out_dir), name_hint="query_selected")

    def _export_all(lang: str):
        records = list(reversed(logger.recent(100)))
        if not records:
            raise gr.Error(_t2s(lang, "hist_empty"))
        import tempfile
        from .text2sql.exporter import export_csv
        out_dir = Path(tempfile.gettempdir()) / "text2sql_exports"
        out_dir.mkdir(exist_ok=True)
        columns = ["Time", "Question", "Status", "Elapsed(ms)", "SQL"]
        rows = [(r.get("timestamp", ""), r.get("user_query", ""),
                 r.get("status", ""), r.get("exec_time_ms", ""),
                 r.get("generated_sql", "")) for r in records]
        return export_csv(columns=columns, rows=rows, path=str(out_dir), name_hint="query_history_all")

    def _switch_lang(choice):
        lang = "zh" if choice == "中文" else "en"
        if lang == "zh":
            return (lang,
                    gr.update(value="## 查询历史"),
                    gr.update(value="💬 恢复会话"),
                    gr.update(value="← 返回"),
                    gr.update(value="↻ 刷新"),
                    gr.update(value="⭐ 收藏此查询"),
                    gr.update(label="📥 导出所选"),
                    gr.update(label="📥 导出全部"),
                    gr.update(value="✕ 删除所选"),
                    gr.update(value="清空全部"))
        return (lang,
                gr.update(value="## Query History"),
                gr.update(value="💬 Resume Chat"),
                gr.update(value="← Back"),
                gr.update(value="↻ Refresh"),
                gr.update(value="⭐ Save to Favorites"),
                gr.update(label="📥 Export Selected"),
                gr.update(label="📥 Export All CSV"),
                gr.update(value="✕ Delete Selected"),
                gr.update(value="Clear All"))

    _sel_outputs = [selected_state, selected_info, detail_html]
    _refresh_outputs = [history_table, selected_state, selected_info, detail_html]

    lang_dd.change(
        fn=_switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, resume_btn, back_btn, refresh_btn, save_fav_btn, export_sel_btn, export_all_btn, delete_btn, clear_btn],
    )
    history_table.select(
        fn=_on_select,
        inputs=[selected_state],
        outputs=_sel_outputs,
    )
    selected_idx_box.input(
        fn=_on_js_select,
        inputs=[selected_idx_box],
        outputs=_sel_outputs,
    )
    def _resume_set(choice: str):
        if not choice:
            return
        parts = choice.rsplit("[", 1)
        if len(parts) < 2:
            return
        sid = parts[1].rstrip("]").strip()
        if sid:
            with _shared_holder_lock:
                _shared_holder["_pending_resume"] = sid

    _RESUME_OPEN_JS = "() => { window.open('/text2sql', '_blank'); }"
    resume_btn.click(fn=_resume_set, inputs=[session_dd]).then(
        fn=None, js=_RESUME_OPEN_JS,
    )

    def _refresh_sessions():
        return gr.update(choices=_session_choices_global(), value=None)

    refresh_btn.click(fn=_refresh, outputs=_refresh_outputs)
    refresh_btn.click(fn=_refresh_sessions, outputs=[session_dd])
    save_fav_btn.click(fn=_save_to_favorites, inputs=[selected_state, lang_state])
    export_sel_btn.click(fn=_export_selected, inputs=[selected_state, lang_state], outputs=[export_sel_btn])
    export_all_btn.click(fn=_export_all, inputs=[lang_state], outputs=[export_all_btn])
    delete_btn.click(
        fn=_delete_selected,
        inputs=[selected_state],
        outputs=_refresh_outputs,
    )
    clear_btn.click(fn=_clear, outputs=_refresh_outputs)

    if app is not None:
        app.load(fn=_refresh, outputs=_refresh_outputs)
        app.load(fn=None, js=_HIST_ROW_HL_JS)

    history_table.change(fn=None, js=_HIST_ROW_HL_JS)


def _fav_rows(store: FavoritesStore) -> list[list[str]]:
    rows = []
    for i, e in enumerate(store.list()):
        sql = e.get("sql", "")
        rows.append([
            str(i),
            e.get("name", ""),
            e.get("ds_type", ""),
            sql,
            e.get("created_at", "").replace("T", " "),
        ])
    return rows


def render_favorites_page(app=None) -> None:
    """Full-page SQL favorites viewer."""
    store = FavoritesStore()

    _ROW_HL_JS = """
    () => {
      requestAnimationFrame(() => {
        document.querySelectorAll('.st-fav-table table tbody tr').forEach(tr => {
          if (tr.dataset._hlBound) return;
          tr.dataset._hlBound = '1';
          tr.style.cursor = 'pointer';
          tr.addEventListener('click', () => {
            tr.classList.toggle('st-row-selected');
            document.querySelectorAll('.st-fav-table table tbody tr').forEach(r => {
              if (r !== tr) r.classList.remove('st-row-selected');
            });
          });
        });
      });
    }
    """

    with gr.Column(elem_classes=["st-history-page"]):
        lang_state = gr.State("en")
        with gr.Row(elem_classes=["st-topbar-row"]):
            gr.HTML('<div class="st-topbar-spacer"></div>')
            lang_dd = gr.Dropdown(
                choices=["English", "中文"],
                value="English",
                show_label=False,
                container=False,
                min_width=140,
                elem_classes=["st-lang-dd"],
            )

        title_md = gr.Markdown("#### ⭐ SQL Favorites")

        with gr.Row(elem_classes=["st-hist-toolbar"]):
            back_btn = gr.Button("← Back", variant="secondary", size="sm",
                                 elem_classes=["st-hist-btn"])
            refresh_btn = gr.Button("↻", variant="secondary", size="sm",
                                    elem_classes=["st-hist-btn"])
            fav_search = gr.Textbox(
                placeholder=_t2s("en", "fav_search_placeholder"),
                show_label=False, lines=1, scale=3,
                elem_classes=["st-table-search"],
            )
            search_clear_btn = gr.Button("✕", size="sm", scale=0, min_width=32)
            rename_input = gr.Textbox(
                placeholder=_t2s("en", "fav_rename_placeholder"),
                show_label=False, lines=1, scale=2,
                interactive=True,
            )
            rename_save_btn = gr.Button("✓", variant="primary", size="sm",
                                        scale=0, min_width=36)
            delete_btn = gr.Button("✕ Delete", variant="stop", size="sm",
                                   elem_classes=["st-hist-btn"])
            clear_btn = gr.Button("Clear All", variant="stop", size="sm",
                                  elem_classes=["st-hist-btn"])

        selected_state = gr.State([])
        search_state = gr.State("")
        selected_info = gr.Markdown("", elem_classes=["st-hist-sel-info"])

        fav_table = gr.Dataframe(
            headers=["#", "Name", "Engine", "SQL", "Created"],
            value=_fav_rows(store),
            interactive=False,
            wrap=True,
            column_widths=["30px", "15%", "50px", "55%", "100px"],
            elem_classes=["st-fav-table"],
        )

        gr.HTML(
            '<style>'
            '.st-fav-table table tbody tr.st-row-selected { background: var(--color-accent-soft, #dbeafe) !important; }'
            '@media (prefers-color-scheme: dark) { .st-fav-table table tbody tr.st-row-selected { background: #1e3a5f !important; } }'
            '</style>'
        )

    def _filtered_rows(query: str = "") -> list[list[str]]:
        all_rows = _fav_rows(store)
        if not query or not query.strip():
            return all_rows
        low = query.lower()
        return [r for r in all_rows if low in r[1].lower() or low in r[3].lower()]

    def _on_select(evt: gr.SelectData, current: list, search_q: str):
        row = evt.index[0]
        current = [row]
        visible = _filtered_rows(search_q)
        name = ""
        if 0 <= row < len(visible):
            name = visible[row][1]
        info = f"**Selected:** #{row}"
        return current, info, gr.update(value=name)

    def _refresh(search_q: str = ""):
        return _filtered_rows(search_q), [], "", gr.update(value="")

    def _clear_search():
        return _fav_rows(store), gr.update(value=""), "", [], "", gr.update(value="")

    def _on_search(query: str):
        return _filtered_rows(query), query, [], "", gr.update(value="")

    def _delete_selected(selected: list, search_q: str):
        if selected:
            visible = _filtered_rows(search_q)
            items = store.list()
            for idx in sorted(selected, reverse=True):
                if 0 <= idx < len(visible):
                    orig_idx = int(visible[idx][0])
                    if 0 <= orig_idx < len(items):
                        store.delete(items[orig_idx]["id"])
        return _filtered_rows(search_q), [], "", gr.update(value="")

    def _clear():
        for item in store.list():
            store.delete(item["id"])
        return [], [], "", gr.update(value="")

    def _do_rename(new_name: str, selected: list, search_q: str, lang: str):
        if not selected:
            gr.Warning(_t2s(lang, "fav_rename_no_selection"))
            return gr.update(), gr.update()
        if not new_name.strip():
            gr.Warning(_t2s(lang, "fav_rename_empty"))
            return gr.update(), gr.update()
        visible = _filtered_rows(search_q)
        items = store.list()
        idx = selected[0]
        if 0 <= idx < len(visible):
            orig_idx = int(visible[idx][0])
            if 0 <= orig_idx < len(items):
                store.rename(items[orig_idx]["id"], new_name.strip())
                gr.Info(_t2s(lang, "fav_rename_ok").format(name=new_name.strip()))
        return _filtered_rows(search_q), ""

    def _switch_lang(choice):
        lang = "zh" if choice == "中文" else "en"
        if lang == "zh":
            return (lang,
                    gr.update(value="#### ⭐ SQL 收藏夹"),
                    gr.update(placeholder=_t2s("zh", "fav_search_placeholder")),
                    gr.update(value="← 返回"),
                    gr.update(value="↻"),
                    gr.update(value="✕ 删除"),
                    gr.update(value="清空全部"),
                    gr.update(placeholder=_t2s("zh", "fav_rename_placeholder")),
                    gr.update(value="✓"))
        return (lang,
                gr.update(value="#### ⭐ SQL Favorites"),
                gr.update(placeholder=_t2s("en", "fav_search_placeholder")),
                gr.update(value="← Back"),
                gr.update(value="↻"),
                gr.update(value="✕ Delete"),
                gr.update(value="Clear All"),
                gr.update(placeholder=_t2s("en", "fav_rename_placeholder")),
                gr.update(value="✓"))

    lang_dd.change(
        fn=_switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, fav_search, back_btn, refresh_btn,
                 delete_btn, clear_btn, rename_input, rename_save_btn],
    )
    fav_table.select(
        fn=_on_select,
        inputs=[selected_state, search_state],
        outputs=[selected_state, selected_info, rename_input],
    )
    fav_search.input(
        fn=_on_search,
        inputs=[fav_search],
        outputs=[fav_table, search_state, selected_state, selected_info, rename_input],
    )
    back_btn.click(fn=None, js="() => { window.close(); }")
    search_clear_btn.click(
        fn=_clear_search,
        outputs=[fav_table, fav_search, search_state, selected_state, selected_info, rename_input],
    )
    refresh_btn.click(fn=_refresh, inputs=[search_state],
                      outputs=[fav_table, selected_state, selected_info, rename_input])
    rename_save_btn.click(
        fn=_do_rename,
        inputs=[rename_input, selected_state, search_state, lang_state],
        outputs=[fav_table, selected_info],
    )
    delete_btn.click(
        fn=_delete_selected,
        inputs=[selected_state, search_state],
        outputs=[fav_table, selected_state, selected_info, rename_input],
    )
    clear_btn.click(fn=_clear, outputs=[fav_table, selected_state, selected_info, rename_input])

    if app is not None:
        app.load(fn=_refresh, inputs=[search_state],
                 outputs=[fav_table, selected_state, selected_info, rename_input])
        app.load(fn=None, js=_ROW_HL_JS)

    fav_table.change(fn=None, js=_ROW_HL_JS)


def _placeholder(lang: str = "en") -> str:
    hints = HINTS_I18N.get(lang, HINTS_I18N["en"])
    cards = "\n".join(f'<div class="st-hint-card">{h}</div>' for h in hints)
    title = _t2s(lang, "placeholder_title")
    return f'''<div class="st-empty-state">
  <div class="st-empty-logo" style="background:#0ea5e9;">SQL</div>
  <div class="st-empty-title">{title}</div>
  <div class="st-empty-hints">{cards}</div>
</div>'''


def render_text2sql_page(app=None) -> None:
    """Render the Text2SQL page components (call inside an app.route block)."""
    from dotenv import load_dotenv
    load_dotenv()

    lang = "en"
    t = lambda k: _t2s(lang, k)

    holder: dict[str, Any] = {
        "agent": None,
        "collector": None,
        "settings": None,
        "store": None,
        "full_store": None,
        "ds_type": "hive",
        "db_config": None,
        "session_id": None,
    }
    holder_lock = threading.Lock()

    def _table_choices(store, lang="zh"):
        """Build CheckboxGroup choices from a SchemaStore."""
        choices = []
        for tb in store.tables:
            if lang == "zh" and tb.comment:
                label = f"{tb.name} ({tb.comment})"
            else:
                label = tb.name
            choices.append(label)
        return choices

    def _sync_agent_store(new_store):
        """Update agent's runtime store AND rebuild its system prompt."""
        agent = holder.get("agent")
        if agent is not None:
            from .text2sql.prompts import build_text2sql_prompt
            agent.runtime.store = new_store
            ds_type = holder.get("ds_type", "hive")
            agent._system_prompt = build_text2sql_prompt(new_store, dialect=ds_type)
    logger = QueryLogger()
    fav_store = FavoritesStore()

    _DS_CHOICES = [DIALECT_NAMES[d] for d in DS_TYPES]
    _DS_LABEL_TO_KEY = {v: k for k, v in DIALECT_NAMES.items()}
    _NEEDS_AUTH = frozenset({"mysql", "sqlserver", "sparksql", "clickhouse", "doris", "postgresql"})
    _NEEDS_HOST = frozenset({"hive", "mysql", "sqlserver", "sparksql", "clickhouse", "doris", "postgresql"})

    with gr.Row(elem_classes=["st-page-row"]):
        lang_state = gr.State("en")

        # ── Left panel (sidebar) ──
        with gr.Column(scale=0, min_width=260, elem_classes=["st-sidebar"], elem_id="text2sql-sidebar") as sidebar_col:
            sidebar_toggle = gr.Button("☰", size="sm", elem_classes=["st-sidebar-toggle"])
            sidebar_title = gr.Markdown(t("sidebar_title"))
            ds_type_dd = gr.Dropdown(
                choices=_DS_CHOICES,
                value=_DS_CHOICES[0],
                label=t("datasource_type"),
                elem_classes=["st-sidebar-control"],
            )
            host_tb = gr.Textbox(
                label=t("host"),
                value="",
                placeholder="10.0.0.1",
                elem_classes=["st-sidebar-control"],
            )
            port_tb = gr.Textbox(
                label=t("port"),
                value="",
                placeholder="10000",
                elem_classes=["st-sidebar-control"],
            )
            db_tb = gr.Textbox(
                label=t("database"),
                value="",
                placeholder="default",
                elem_classes=["st-sidebar-control"],
            )
            username_tb = gr.Textbox(
                label=t("username"),
                value="",
                placeholder="",
                visible=False,
                elem_classes=["st-sidebar-control"],
            )
            password_tb = gr.Textbox(
                label=t("password"),
                value="",
                placeholder="",
                type="password",
                visible=False,
                elem_classes=["st-sidebar-control"],
            )
            connect_btn = gr.Button(t("connect"), variant="secondary", size="sm",
                                    elem_classes=["st-connect-btn"])
            reload_schema_btn = gr.Button(
                t("reload_schema"),
                size="sm",
                elem_classes=["st-connect-btn"],
            )
            with gr.Accordion(
                t("select_tables").format(n=0), open=False, visible=True,
                elem_classes=["st-filter-accordion"],
            ) as filter_accordion:
                table_search = gr.Textbox(
                    placeholder=t("search_placeholder"),
                    show_label=False, lines=1,
                    elem_classes=["st-table-search"],
                )
                table_filter = gr.CheckboxGroup(
                    choices=[], label="", show_label=False,
                    elem_classes=["st-table-filter"],
                )
                with gr.Row(elem_classes=["st-filter-actions"]):
                    select_all_btn = gr.Button(
                        t("select_all"), size="sm",
                        elem_classes=["st-filter-act-btn"],
                    )
                    deselect_all_btn = gr.Button(
                        t("deselect_all"), size="sm",
                        elem_classes=["st-filter-act-btn"],
                    )
                with gr.Row(elem_classes=["st-filter-confirm-row"]):
                    confirm_filter_btn = gr.Button(
                        f"✔ {t('confirm')}", variant="primary", size="sm",
                        elem_classes=["st-filter-confirm-btn"],
                    )
                    cancel_filter_btn = gr.Button(
                        f"✕ {t('cancel')}", size="sm",
                        elem_classes=["st-filter-cancel-btn"],
                    )
            schema_browse_btn = gr.Button(
                t("schema_browse_btn"), size="sm",
                elem_classes=["st-filter-act-btn"],
            )
            schema_browse_btn.click(
                fn=None,
                js="() => { window.open('/schema-browser', '_blank'); }",
            )

            status_box = gr.Textbox(label=t("status_label"), interactive=False,
                                    value=t("status_default"),
                                    elem_classes=["st-sidebar-status"])
            new_chat_btn = gr.Button(t("new_chat"), variant="primary", size="sm",
                                     elem_classes=["st-new-chat-btn"])
            history_link = gr.Button(t("history"), variant="secondary", size="sm",
                                     elem_classes=["st-connect-btn"])
            history_link.click(fn=None, js="() => { window.open('/history', '_blank'); }")

            fav_section_md = gr.Markdown(f"**{t('fav_section_title')}**")
            save_fav_btn = gr.Button(
                t("save_favorite"), variant="primary", size="sm",
                elem_classes=["st-connect-btn"],
            )
            fav_link = gr.Button(t("favorites"), variant="secondary", size="sm",
                                 elem_classes=["st-connect-btn"])
            fav_link.click(fn=None, js="() => { window.open('/favorites', '_blank'); }")

            gr.Markdown(f"**{t('template_label')}**")
            template_dd = gr.Dropdown(
                choices=template_choices("en"),
                value=None,
                label=t("template_label"),
                show_label=False,
                elem_classes=["st-sidebar-control"],
            )
            template_preview = gr.Markdown("", elem_classes=["st-template-preview"])

            gr.Markdown(f"**{t('session_label')}**")
            session_dd = gr.Dropdown(
                choices=[], value=None,
                label=t("session_label"),
                show_label=False,
                elem_classes=["st-sidebar-control"],
            )
            with gr.Row(elem_classes=["st-sidebar-row"]):
                load_session_btn = gr.Button(t("load_session"), size="sm",
                                             elem_classes=["st-filter-act-btn"])
                delete_session_btn = gr.Button(t("delete_session"), variant="stop", size="sm",
                                               elem_classes=["st-filter-act-btn"])

        # ── Right panel (chat) ──
        with gr.Column(scale=1, elem_classes=["st-main"]):
            with gr.Row(elem_classes=["st-topbar-row"]):
                sidebar_open_btn = gr.Button("☰", size="sm", visible=False, elem_classes=["st-sidebar-open-btn"])
                gr.HTML('<div class="st-topbar-spacer"></div>')
                home_btn = gr.Button("\U0001f3e0", size="sm", elem_classes=["st-home-btn"])
                lang_dd = gr.Dropdown(
                    choices=["English", "中文"],
                    value="English",
                    show_label=False,
                    container=False,
                    min_width=140,
                    elem_classes=["st-lang-dd"],
                )

            chatbot = gr.Chatbot(
                show_label=False,
                placeholder=_placeholder(lang),
                layout="panel",
                buttons=["copy"],
                elem_classes=["st-chatbot"],
                height=None,
                sanitize_html=False,
            )
            with gr.Row(visible=False, elem_classes=["st-dl-row"]) as dl_row:
                export_btn = gr.DownloadButton(
                    "📥 CSV", variant="secondary", size="sm",
                    elem_classes=["st-dl-btn"], scale=0, min_width=80,
                )
                chart_dl_btn = gr.DownloadButton(
                    "🖼️ Chart", variant="secondary", size="sm",
                    elem_classes=["st-dl-btn"], scale=0, min_width=80,
                )
            chart_plot = gr.Plot(visible=False, elem_classes=["st-chart"], show_label=False)
            def _chart_choices(lang):
                _t = lambda k: _t2s(lang, k)
                return [_t("chart_auto"), _t("chart_bar"), _t("chart_line"),
                        _t("chart_pie"), _t("chart_scatter"), _t("chart_none")]

            chart_type_radio = gr.Radio(
                choices=_chart_choices("en"),
                value=_t2s("en", "chart_auto"),
                label=t("chart_type_label"),
                elem_classes=["st-chart-type"],
            )
            page_table_md = gr.Markdown("", visible=False, elem_classes=["st-page-table"])
            with gr.Row(visible=False, elem_classes=["st-page-nav"]) as page_nav_row:
                prev_page_btn = gr.Button(t("prev_page"), size="sm", scale=0, min_width=80)
                page_info_md = gr.Markdown("", elem_classes=["st-page-info"])
                next_page_btn = gr.Button(t("next_page"), size="sm", scale=0, min_width=80)
            page_state = gr.State(1)
            with gr.Row(elem_classes=["st-input-row"]):
                user_input = gr.Textbox(
                    placeholder=t("input_placeholder"),
                    show_label=False, scale=8, lines=1,
                    elem_classes=["st-input"],
                )
                send_btn = gr.Button("➤", variant="primary", size="sm", scale=0,
                                     min_width=48, elem_classes=["st-btn-send"])
                stop_btn = gr.Button("■", variant="stop", size="sm", scale=0,
                                     min_width=48, visible=False, elem_classes=["st-btn-stop"])

    # ── Datasource type change callback ──
    def _on_ds_change(ds_label: str):
        ds = _DS_LABEL_TO_KEY.get(ds_label, "hive")
        defaults = DS_DEFAULTS.get(ds, {})
        default_port = str(defaults.get("port", 10000))
        default_db = defaults.get("database", "default")
        show_auth = ds in _NEEDS_AUTH
        show_host = ds in _NEEDS_HOST

        env_cfg = config_from_env(ds)
        if env_cfg:
            return (
                gr.update(value=str(env_cfg.port), placeholder=default_port, visible=show_host),
                gr.update(value=env_cfg.database, placeholder=str(default_db), visible=True),
                gr.update(value=env_cfg.host, visible=show_host),
                gr.update(value=env_cfg.username or "", visible=show_auth),
                gr.update(value=env_cfg.password or "", visible=show_auth),
            )
        db_placeholder = "config/demo.db" if ds == "sqlite" else str(default_db)
        return (
            gr.update(value="", placeholder=default_port, visible=show_host),
            gr.update(value="", placeholder=db_placeholder, visible=True),
            gr.update(value="", visible=show_host),
            gr.update(value="", visible=show_auth),
            gr.update(value="", visible=show_auth),
        )

    ds_type_dd.change(
        fn=_on_ds_change,
        inputs=[ds_type_dd],
        outputs=[port_tb, db_tb, host_tb, username_tb, password_tb],
    )

    # ── Sidebar toggle ──
    def _close_sidebar():
        return gr.update(visible=False), gr.update(visible=True)

    def _open_sidebar():
        return gr.update(visible=True), gr.update(visible=False)

    sidebar_toggle.click(fn=_close_sidebar, outputs=[sidebar_col, sidebar_open_btn])
    sidebar_open_btn.click(fn=_open_sidebar, outputs=[sidebar_col, sidebar_open_btn])

    # ── Callbacks ──

    def _connect(ds_label: str, host: str, port: str,
                 db: str, username: str, password: str, lang: str):
        t = lambda k: _t2s(lang, k)
        no = gr.update()
        def err(msg):
            return (msg, no, no, no, no, no, no, no, no)

        ds_type = _DS_LABEL_TO_KEY.get(ds_label, "hive")

        try:
            settings = load_settings()
        except Exception as e:
            return err(f"❌ {t('llm_load_fail')}: {e}")

        # ── Build DatabaseConfig ──
        db_config = None
        h = host.strip()
        p = port.strip()
        d = db.strip()
        u = username.strip() or None
        pw = password.strip() or None

        defaults = DS_DEFAULTS.get(ds_type, {})
        default_port = str(defaults.get("port", 10000))
        default_db = defaults.get("database", "default")

        if not h and ds_type in _NEEDS_HOST:
            fallback = config_from_env(ds_type)
            if fallback:
                h, p, d = fallback.host, str(fallback.port), fallback.database
                u = fallback.username
                pw = fallback.password

        if ds_type == "sqlite":
            db_config = DatabaseConfig(
                ds_type="sqlite",
                host="",
                port=0,
                database=d or str(default_db),
            )
        elif h and ds_type in _NEEDS_HOST:
            try:
                db_config = DatabaseConfig(
                    ds_type=ds_type,
                    host=h,
                    port=int(p or default_port),
                    database=d or str(default_db),
                    username=u,
                    password=pw,
                )
            except ValueError:
                return err(f"❌ {t('port_not_number')}")

        # ── Load schema ──
        store = None
        schema_source = ""
        dialect_name = DIALECT_NAMES.get(ds_type, ds_type)
        db_note = ""

        if ds_type == "flinksql":
            db_note = t("flink_generate_only")
            path = Path(schema_ddl_path_from_env())
            if not path.is_file():
                return err(f"❌ {t('schema_not_found')}: {path}")
            try:
                store = SchemaStore.from_file(path)
            except Exception as e:
                return err(f"❌ {t('schema_parse_fail')}: {e}")
            schema_source = t("loaded_tables").format(n=len(store))
        elif db_config:
            executor = create_executor(db_config)
            ok, msg = executor.test_connection()
            if not ok:
                return err(f"❌ {dialect_name}: {msg}")
            db_note = f"✅ {dialect_name} {msg}"
            try:
                store = SchemaStore.from_db(executor)
            except Exception as e:
                return err(f"❌ {t('schema_parse_fail')}: {e}")
            schema_source = t("loaded_from_db").format(
                n=len(store), db_type=dialect_name, db=db_config.database
            )
        else:
            db_note = t("db_not_configured")
            path = Path(schema_ddl_path_from_env())
            if not path.is_file():
                return err(f"❌ {t('schema_not_found')}: {path}")
            try:
                store = SchemaStore.from_file(path)
            except Exception as e:
                return err(f"❌ {t('schema_parse_fail')}: {e}")
            schema_source = t("loaded_tables").format(n=len(store))

        if len(store) == 0:
            return err(f"❌ {t('no_tables')}")

        llm_status = f"⏳ LLM {settings.model_name} (checking...)"

        with holder_lock:
            holder["settings"] = settings
            holder["store"] = store
            holder["full_store"] = store
            holder["ds_type"] = ds_type
            holder["db_config"] = db_config
            holder["agent"] = None
        with _shared_holder_lock:
            _shared_holder["full_store"] = store
            _shared_holder["db_config"] = db_config
            _shared_holder["ds_type"] = ds_type

        def _warmup():
            try:
                from .text2sql.agent import Text2SQLAgent
                agent = Text2SQLAgent(
                    settings, store=store, ds_type=ds_type, db_config=db_config,
                )
                with holder_lock:
                    if holder.get("agent") is None:
                        holder["agent"] = agent
                    resume_msgs = holder.pop("_resume_agent_msgs", None)
                    if resume_msgs:
                        agent.messages = resume_msgs
                    holder["llm_status"] = f"✅ LLM {settings.model_name}"
            except Exception as e:
                e_msg = str(e)
                with holder_lock:
                    if "timeout" in e_msg.lower() or "timed out" in e_msg.lower():
                        holder["llm_status"] = f"⚠️ LLM timeout ({settings.llm_base_url or 'default'})"
                    elif "auth" in e_msg.lower() or "api key" in e_msg.lower() or "401" in e_msg:
                        holder["llm_status"] = f"❌ LLM auth fail — check API_KEY"
                    elif "connect" in e_msg.lower():
                        holder["llm_status"] = f"❌ LLM unreachable ({settings.llm_base_url or 'default'})"
                    else:
                        holder["llm_status"] = f"⚠️ LLM: {e_msg[:80]}"

        threading.Thread(target=_warmup, daemon=True).start()

        status = f"✅ {schema_source} · {db_note} · {llm_status}"

        choices = _table_choices(store, lang)
        holder["last_confirmed"] = list(choices)
        no = gr.update()

        chat_up = no
        input_up = no
        with _shared_holder_lock:
            rsid = _shared_holder.pop("_pending_resume", "")
        if rsid:
            session = load_t2s_session(rsid)
            if session is not None:
                holder["session_id"] = rsid
                holder["_resume_agent_msgs"] = session.agent_messages
                chat_up = session.chat_messages
                input_up = gr.update(value="", placeholder=t("conversation_active"))
                status += f" · 💬 {t('session_resumed')}"

        return (
            status,
            gr.update(value=h) if h else no,
            gr.update(value=p) if p else no,
            gr.update(value=d) if d else no,
            gr.update(choices=choices, value=choices),
            gr.update(open=True, label=t("select_tables").format(n=len(store))),
            choices,
            chat_up,
            input_up,
        )

    _CHART_KEY_TO_TYPE = {"chart_bar": "bar", "chart_line": "line", "chart_pie": "pie", "chart_scatter": "scatter"}

    def _chart_pref_to_type(pref: str, lang: str):
        """Map a localized chart radio label back to a chart type key."""
        for key, ct in _CHART_KEY_TO_TYPE.items():
            if pref == _t2s(lang, key):
                return ct
        return None

    def _run_streaming(msg: str, history: list, lang: str, chart_pref: str = "Auto"):
        from .ui import EventCollector, _normalize_chat
        from .text2sql.chart import detect_chart_type, build_chart, fig_to_base64
        import matplotlib.pyplot as plt

        t = lambda k: _t2s(lang, k)
        history = _normalize_chat(history)
        collector = EventCollector()
        start = time.time()

        with holder_lock:
            holder["collector"] = collector
            store_ref = holder.get("store")
            if holder.get("agent") is None:
                from .text2sql.agent import Text2SQLAgent
                agent = Text2SQLAgent(
                    holder["settings"],
                    store=holder["store"],
                    ds_type=holder.get("ds_type", "hive"),
                    db_config=holder.get("db_config"),
                    on_event=collector.on_event,
                )
                holder["agent"] = agent
            else:
                agent = holder["agent"]
                agent._on_event = collector.on_event

        error_msg = None

        def _worker():
            nonlocal error_msg
            try:
                if not agent.messages:
                    agent.run(msg)
                else:
                    agent.chat(msg)
            except Exception as e:
                error_msg = str(e)
                collector.on_event("final_answer", {"text": f"Error: {e}"})

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        prev = 0
        fmt = _IncrementalFormatter(start, lang, store_ref)
        user_msg = [{"role": "user", "content": msg}]
        while not collector.done:
            collector.wait_for_event(timeout=0.3)
            count = collector.event_count
            if count > prev:
                new_events = collector.snapshot_since(prev)
                prev = count
                yield history + user_msg + fmt.feed(new_events), gr.update()
        thread.join(timeout=120)
        remaining = collector.snapshot_since(prev)
        if remaining:
            fmt.feed(remaining)
        final = fmt.finalize()
        if error_msg:
            final.append({"role": "assistant", "content": f"⚠️ **Error**: {error_msg}"})
        final.append({"role": "assistant", "content": f"⏱️ {t('done')} {time.time() - start:.1f}s"})

        rt = agent.runtime if agent else None
        if rt and rt.last_sql:
            with holder_lock:
                holder["_last_sql"] = rt.last_sql
                last_q = ""
                if agent and agent.messages:
                    for m in reversed(agent.messages):
                        if m.get("role") == "user":
                            last_q = str(m.get("content", ""))[:60]
                            break
                holder["_last_question"] = last_q

        chart_update = gr.update(visible=False)
        if rt and rt.last_result and rt.last_result.columns and rt.last_result.rows:
            if chart_pref == _t2s(lang, "chart_none"):
                ct = None
            elif _chart_pref_to_type(chart_pref, lang):
                ct = _chart_pref_to_type(chart_pref, lang)
            else:
                ct = detect_chart_type(rt.last_result.columns, rt.last_result.rows)
            if ct:
                fig = build_chart(rt.last_result.columns, rt.last_result.rows, ct)
                if fig:
                    data_uri = fig_to_base64(fig)
                    chart_html = (
                        f'<div class="st-inline-chart">'
                        f'<img src="{data_uri}" alt="chart" '
                        f'style="max-width:100%;border-radius:8px;margin:8px 0;" />'
                        f'</div>'
                    )
                    try:
                        import tempfile as _tmp
                        _dl_dir = Path(_tmp.gettempdir()) / "text2sql_exports"
                        _dl_dir.mkdir(parents=True, exist_ok=True)
                        _ts = time.strftime("%Y%m%d_%H%M%S")
                        _png_path = str(_dl_dir / f"chart_{_ts}.png")
                        fig.savefig(_png_path, format="png", bbox_inches="tight", dpi=120)
                        with holder_lock:
                            holder["_last_chart_png"] = _png_path
                    except Exception:
                        pass
                    final.append({"role": "assistant", "content": chart_html})
                    if rt.last_sql:
                        sql_hash = hashlib.md5(rt.last_sql.encode()).hexdigest()
                        _chart_cache_put(sql_hash, data_uri)
                    plt.close(fig)

        yield history + [{"role": "user", "content": msg}] + final, chart_update

    def _handle_submit(msg: str, history: list, lang: str, chart_pref: str = "Auto"):
        t = lambda k: _t2s(lang, k)
        if not msg.strip():
            yield history, gr.update()
            return
        with holder_lock:
            store_ready = holder.get("store") is not None
        if not store_ready:
            yield history + [
                {"role": "user", "content": msg},
                {"role": "assistant", "content": t("connect_first")},
            ], gr.update()
            return
        yield from _run_streaming(msg, history, lang, chart_pref)

    def _handle_stop(lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            c = holder.get("collector")
        if c and not c.done:
            c.on_event("final_answer", {"text": t("stopped")})
        return gr.update(visible=True), gr.update(visible=False)

    def _new_chat(lang):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            agent = holder.get("agent")
            if agent is not None:
                agent.reset()
            holder["session_id"] = None
            holder.pop("_last_chart_png", None)
        return (
            [],
            gr.update(placeholder=t("input_placeholder")),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
            1,
            gr.update(visible=False),
        )

    def _handle_export(lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            agent = holder.get("agent")
        rt = agent.runtime if agent else None
        if rt is None or rt.last_result is None:
            raise gr.Error(t("no_export"))
        import tempfile
        from .text2sql.exporter import export_csv
        out_dir = Path(tempfile.gettempdir()) / "text2sql_exports"
        out_dir.mkdir(exist_ok=True)
        return export_csv(
            columns=rt.last_result.columns,
            rows=rt.last_result.rows,
            path=str(out_dir),
            name_hint="query_result",
        )

    def _handle_chart_dl(lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            png_path = holder.get("_last_chart_png")
        if not png_path or not Path(png_path).is_file():
            raise gr.Error(t("hist_chart_unavailable"))
        return png_path

    def _reload_schema(lang: str):
        t = lambda k: _t2s(lang, k)
        no = gr.update()
        try:
            db_config = holder.get("db_config")
            ds_type = holder.get("ds_type", "hive")
            if db_config and ds_type != "flinksql":
                executor = create_executor(db_config)
                new_store = SchemaStore.from_db(executor)
            else:
                from .text2sql.schema import parse_ddl
                path = Path(schema_ddl_path_from_env())
                if not path.is_file():
                    return f"❌ {t('schema_not_found')}: {path}", no, no, no
                text = path.read_text(encoding="utf-8")
                new_store = SchemaStore(parse_ddl(text))
            with holder_lock:
                holder["store"] = new_store
                holder["full_store"] = new_store
                _sync_agent_store(new_store)
            with _shared_holder_lock:
                _shared_holder["full_store"] = new_store
            agent = holder.get("agent")
            if agent is not None:
                agent.runtime.cache.invalidate()
            choices = _table_choices(new_store, lang)
            holder["last_confirmed"] = list(choices)
            n = len(new_store)
            return (
                t("schema_reloaded").format(n=n),
                gr.update(choices=choices, value=choices),
                gr.update(open=True, label=t("select_tables").format(n=n)),
                choices,
            )
        except Exception as e:
            return f"Error: {e}", no, no, no

    # ── Favorites callback ──

    def _save_favorite(lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            agent = holder.get("agent")
            sql_fallback = holder.get("_last_sql", "")
            last_question = holder.get("_last_question", "")
        rt = agent.runtime if agent else None
        sql = (rt.last_sql if rt else "") or sql_fallback
        if not sql:
            raise gr.Error(t("no_sql_to_save"))
        if not last_question and agent and agent.messages:
            for m in reversed(agent.messages):
                if m.get("role") == "user":
                    last_question = str(m.get("content", ""))[:60]
                    break
        name = last_question or sql[:40]
        fav_store.save(
            name=name,
            sql=sql,
            question=last_question,
            ds_type=holder.get("ds_type", ""),
        )
        gr.Info(t("favorite_saved"))

    def _apply_filter(selected: list, lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            full = holder.get("full_store")
        if not full:
            return t("status_default")
        if not selected:
            with holder_lock:
                holder["store"] = SchemaStore([])
                _sync_agent_store(holder["store"])
            return f"❌ {t('no_tables')}"
        sel_names = set()
        for label in selected:
            name = label.split("(")[0].strip()
            sel_names.add(name.lower())
        filtered = [tb for tb in full.tables if tb.name.lower() in sel_names]
        new_store = SchemaStore(filtered)
        with holder_lock:
            holder["store"] = new_store
            _sync_agent_store(new_store)
        n = len(new_store)
        total = len(full)
        if n == total:
            return f"✅ {t('select_tables').format(n=total)}"
        return f"✅ {t('filtered_tables').format(n=n)}"

    def _switch_lang(choice, cur_selected):
        lang = "zh" if choice == "中文" else "en"
        t = lambda k: _t2s(lang, k)
        full = holder.get("full_store")
        n = len(full) if full else 0
        sel_names = set()
        for label in (cur_selected or []):
            sel_names.add(label.split("(")[0].strip().lower())
        choices = _table_choices(full, lang) if full else []
        new_selected = [c for c in choices if c.split("(")[0].strip().lower() in sel_names]
        return (
            lang,
            gr.update(value=t("sidebar_title")),
            gr.update(label=t("datasource_type")),
            gr.update(label=t("host")),
            gr.update(label=t("port")),
            gr.update(label=t("database")),
            gr.update(label=t("username")),
            gr.update(label=t("password")),
            gr.update(value=t("connect")),
            gr.update(label=t("status_label")),
            gr.update(value=t("new_chat")),
            gr.update(value=t("history")),
            gr.update(placeholder=t("input_placeholder")),
            gr.update(placeholder=_placeholder(lang)),
            gr.update(value=t("reload_schema")),
            gr.update(label=t("select_tables").format(n=n)),
            gr.update(value=t("select_all")),
            gr.update(value=t("deselect_all")),
            gr.update(value=f"✔ {t('confirm')}"),
            gr.update(value=f"✕ {t('cancel')}"),
            gr.update(placeholder=t("search_placeholder")),
            gr.update(choices=choices, value=new_selected),
            gr.update(value=f"**{t('fav_section_title')}**"),
            gr.update(value=t("save_favorite")),
            gr.update(value=t("favorites")),
            gr.update(label=t("chart_type_label"), choices=_chart_choices(lang), value=t("chart_auto")),
            gr.update(choices=template_choices(lang), value=None),
            gr.update(value=""),
            gr.update(label=t("session_label")),
            gr.update(value=t("load_session")),
            gr.update(value=t("delete_session")),
            gr.update(value=t("schema_browse_btn")),
        )

    # ── Wiring ──
    confirmed_sel = gr.State([])

    lang_dd.change(
        fn=_switch_lang,
        inputs=[lang_dd, table_filter],
        outputs=[
            lang_state,
            sidebar_title,
            ds_type_dd,
            host_tb,
            port_tb,
            db_tb,
            username_tb,
            password_tb,
            connect_btn,
            status_box,
            new_chat_btn,
            history_link,
            user_input,
            chatbot,
            reload_schema_btn,
            filter_accordion,
            select_all_btn,
            deselect_all_btn,
            confirm_filter_btn,
            cancel_filter_btn,
            table_search,
            table_filter,
            fav_section_md,
            save_fav_btn,
            fav_link,
            chart_type_radio,
            template_dd,
            template_preview,
            session_dd,
            load_session_btn,
            delete_session_btn,
            schema_browse_btn,
        ],
    )

    connect_btn.click(
        fn=_connect,
        inputs=[ds_type_dd, host_tb, port_tb, db_tb,
                username_tb, password_tb, lang_state],
        outputs=[status_box, host_tb, port_tb, db_tb,
                 table_filter, filter_accordion, confirmed_sel,
                 chatbot, user_input],
    )

    def _show_stop():
        return gr.update(visible=False), gr.update(visible=True)

    def _post_submit(lang, history):
        t = lambda k: _t2s(lang, k)
        try:
            _save_current_session(history)
        except Exception:
            pass
        page_vis, page_info_val, page_num = _show_pagination(lang)
        llm_st = holder.get("llm_status")
        status_upd = gr.update(value=llm_st) if llm_st else gr.update()
        with holder_lock:
            agent = holder.get("agent")
        rt = agent.runtime if agent else None
        has_result = rt is not None and rt.last_result is not None
        return (
            gr.update(value="", placeholder=t("conversation_active")),
            gr.update(visible=True),
            gr.update(visible=False),
            page_vis,
            page_info_val,
            page_num,
            gr.update(visible=False),
            gr.update(choices=_session_choices()),
            status_upd,
            gr.update(visible=has_result),
        )

    submit_io = dict(fn=_handle_submit, inputs=[user_input, chatbot, lang_state, chart_type_radio], outputs=[chatbot, chart_plot])
    _post_outputs = [user_input, send_btn, stop_btn, page_nav_row, page_info_md, page_state, page_table_md, session_dd, status_box, dl_row]
    send_btn.click(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, inputs=[lang_state, chatbot], outputs=_post_outputs)
    user_input.submit(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, inputs=[lang_state, chatbot], outputs=_post_outputs)

    stop_btn.click(fn=_handle_stop, inputs=[lang_state], outputs=[send_btn, stop_btn])
    new_chat_btn.click(fn=_new_chat, inputs=[lang_state],
                       outputs=[chatbot, user_input, chart_plot, page_nav_row, page_table_md, page_state, dl_row])
    export_btn.click(fn=_handle_export, inputs=[lang_state], outputs=export_btn)
    chart_dl_btn.click(fn=_handle_chart_dl, inputs=[lang_state], outputs=chart_dl_btn)
    reload_schema_btn.click(fn=_reload_schema, inputs=[lang_state],
                            outputs=[status_box, table_filter, filter_accordion, confirmed_sel])

    save_fav_btn.click(fn=_save_favorite, inputs=[lang_state])

    def _on_template_select(choice: str, lang: str):
        if not choice:
            return gr.update(), gr.update()
        tid = choice.rsplit("[", 1)[-1].rstrip("]").strip()
        desc = template_description(tid, lang)
        tmpl = None
        for candidate in SQL_TEMPLATES:
            if candidate["id"] == tid:
                tmpl = candidate
                break
        if tmpl is None:
            return gr.update(), gr.update()
        name_key = "name_zh" if lang == "zh" else "name_en"
        if lang == "zh":
            hint = f"使用 {tmpl[name_key]} 模式来分析 "
        else:
            hint = f"Use the {tmpl[name_key]} pattern to analyze "
        return gr.update(value=desc), gr.update(value=hint)

    template_dd.change(
        fn=_on_template_select, inputs=[template_dd, lang_state],
        outputs=[template_preview, user_input],
    )

    def _select_all(lang):
        with holder_lock:
            full = holder.get("full_store")
        if not full:
            return gr.update()
        visible = holder.get("search_visible")
        if visible is not None:
            return gr.update(value=list(visible))
        return gr.update(value=_table_choices(full, lang))

    def _deselect_all():
        return gr.update(value=[])

    def _restore_from_search(current_selection, lang):
        """Exit search mode and return the merged full choices + selection."""
        full = holder.get("full_store")
        backup = holder.pop("search_backup", None)
        last_visible = holder.pop("search_visible", None)
        if not full:
            return current_selection or []
        all_choices = _table_choices(full, lang)
        if backup is None:
            return current_selection or []
        current_set = set(current_selection or [])
        backup_set = set(backup)
        visible_set = set(last_visible) if last_visible else set()
        final = []
        for item in all_choices:
            if item in visible_set:
                if item in current_set:
                    final.append(item)
            else:
                if item in backup_set:
                    final.append(item)
        return final

    def _confirm_filter(selected, lang):
        t = lambda k: _t2s(lang, k)
        merged = _restore_from_search(selected, lang)
        status = _apply_filter(merged, lang)
        n = len(merged)
        holder["last_confirmed"] = list(merged)
        full = holder.get("full_store")
        all_choices = _table_choices(full, lang) if full else []
        return status, list(merged), gr.update(label=t("select_tables").format(n=n)), \
               gr.update(choices=all_choices, value=merged), gr.update(value="")

    def _cancel_filter(confirmed, lang):
        full = holder.get("full_store")
        all_choices = _table_choices(full, lang) if full else []
        backup = holder.pop("search_backup", None)
        holder.pop("search_visible", None)
        restore = backup if backup is not None else confirmed
        return gr.update(choices=all_choices, value=restore), gr.update(value="")

    select_all_btn.click(fn=_select_all, inputs=[lang_state], outputs=[table_filter])
    deselect_all_btn.click(fn=_deselect_all, outputs=[table_filter])
    confirm_filter_btn.click(
        fn=_confirm_filter, inputs=[table_filter, lang_state],
        outputs=[status_box, confirmed_sel, filter_accordion, table_filter, table_search],
    )
    cancel_filter_btn.click(
        fn=_cancel_filter, inputs=[confirmed_sel, lang_state],
        outputs=[table_filter, table_search],
    )

    # ── Session management ──

    _session_choices = _session_choices_global

    def _refresh_sessions():
        return gr.update(choices=_session_choices(), value=None)

    def _save_current_session(chat_messages: list):
        sid = holder.get("session_id")
        agent = holder.get("agent")
        if not chat_messages:
            return
        created = now_iso()
        if sid is None:
            sid = new_session_id()
            holder["session_id"] = sid
        else:
            existing = load_t2s_session(sid)
            if existing is not None:
                created = existing.created_at
        session = Text2SQLSession(
            session_id=sid,
            title=extract_title(chat_messages),
            created_at=created,
            updated_at=now_iso(),
            ds_type=holder.get("ds_type", ""),
            chat_messages=chat_messages,
            agent_messages=agent.messages if agent else [],
        )
        save_t2s_session(session)

    def _load_session_handler(session_choice: str, lang: str):
        t = lambda k: _t2s(lang, k)
        if not session_choice:
            return gr.update(), gr.update()
        sid_match = session_choice.rsplit("[", 1)
        if len(sid_match) < 2:
            return gr.update(), gr.update()
        sid = sid_match[1].rstrip("]")
        session = load_t2s_session(sid)
        if session is None:
            return gr.update(), gr.update()
        holder["session_id"] = sid
        agent = holder.get("agent")
        if agent is not None:
            agent.messages = session.agent_messages
        return session.chat_messages, gr.update(value="", placeholder=t("conversation_active"))

    def _delete_session_handler(session_choice: str):
        if not session_choice:
            return gr.update()
        sid_match = session_choice.rsplit("[", 1)
        if len(sid_match) < 2:
            return gr.update()
        sid = sid_match[1].rstrip("]")
        delete_t2s_session(sid)
        return gr.update(choices=_session_choices(), value=None)

    load_session_btn.click(
        fn=_load_session_handler, inputs=[session_dd, lang_state],
        outputs=[chatbot, user_input],
    )
    delete_session_btn.click(
        fn=_delete_session_handler, inputs=[session_dd],
        outputs=[session_dd],
    )

    _PAGE_SIZE = 50

    def _paginate(page: int, lang: str):
        t = lambda k: _t2s(lang, k)
        agent = holder.get("agent")
        rt = agent.runtime if agent else None
        if rt is None or rt.last_result is None:
            return gr.update(), gr.update(), page
        total = rt.last_result.row_count
        total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
        page = max(1, min(page, total_pages))
        start = (page - 1) * _PAGE_SIZE
        end = start + _PAGE_SIZE
        page_rows = rt.last_result.rows[start:end]
        table = _md_table(rt.last_result.columns, [list(r) for r in page_rows], max_rows=_PAGE_SIZE, lang=lang)
        info = t("page_label").format(page=page, total=total_pages) + f" · {t('page_info').format(total=total)}"
        return gr.update(value=table), gr.update(value=info), page

    def _next_page(page: int, lang: str):
        return _paginate(page + 1, lang)

    def _prev_page(page: int, lang: str):
        return _paginate(page - 1, lang)

    def _show_pagination(lang: str):
        t = lambda k: _t2s(lang, k)
        agent = holder.get("agent")
        rt = agent.runtime if agent else None
        if rt and rt.last_result and rt.last_result.row_count > _PREVIEW_ROWS_UI:
            total = rt.last_result.row_count
            total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
            info = t("page_label").format(page=1, total=total_pages) + f" · {t('page_info').format(total=total)}"
            return gr.update(visible=True), gr.update(value=info), 1
        return gr.update(visible=False), gr.update(value=""), 1

    _PREVIEW_ROWS_UI = 20

    def _on_table_search(query, lang):
        full = holder.get("full_store")
        if not full:
            return gr.update()
        all_choices = _table_choices(full, lang)
        if not query or not query.strip():
            backup = holder.get("search_backup")
            if backup is not None:
                holder.pop("search_visible", None)
                return gr.update(choices=all_choices, value=backup)
            return gr.update()
        if "search_backup" not in holder:
            holder["search_backup"] = list(holder.get("last_confirmed") or all_choices)
        low = query.lower()
        filtered = [c for c in all_choices if low in c.lower()]
        holder["search_visible"] = filtered
        kept = [s for s in holder["search_backup"] if s in filtered]
        return gr.update(choices=filtered, value=kept)

    table_search.input(
        fn=_on_table_search,
        inputs=[table_search, lang_state],
        outputs=[table_filter],
    )

    # ── Pagination ──
    prev_page_btn.click(
        fn=_prev_page, inputs=[page_state, lang_state],
        outputs=[page_table_md, page_info_md, page_state],
    )
    next_page_btn.click(
        fn=_next_page, inputs=[page_state, lang_state],
        outputs=[page_table_md, page_info_md, page_state],
    )

    # ── Home button ──
    home_btn.click(fn=None, js="() => { window.location.href = '/'; }")

    # ── Session resume from history page ──

    # ── Load JS from external files ──
    _res = Path(__file__).resolve().parent / "text2sql" / "resources"
    _sidebar_fix_js = (_res / "sidebar_fix.js").read_text(encoding="utf-8")
    _hint_delegate_js = (_res / "hint_delegate.js").read_text(encoding="utf-8")
    _tab_fill_js = (_res / "tab_fill.js").read_text(encoding="utf-8")
    def _auto_resume_on_load(lang: str):
        with _shared_holder_lock:
            sid = _shared_holder.pop("_pending_resume", "")
        if not sid:
            return gr.update(), gr.update(), gr.update()
        session = load_t2s_session(sid)
        if session is None:
            return gr.update(), gr.update(), gr.update()
        t = lambda k: _t2s(lang, k)
        holder["session_id"] = sid
        holder["_resume_agent_msgs"] = session.agent_messages

        def _msg_text(content):
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in content
                )
            return str(content)

        for m in reversed(session.chat_messages):
            if m.get("role") == "assistant":
                text = _msg_text(m.get("content", ""))
                sql_match = re.search(r"```sql\s*\n(.*?)```", text, re.S)
                if sql_match:
                    holder["_last_sql"] = sql_match.group(1).strip()
                    break
        for m in reversed(session.chat_messages):
            if m.get("role") == "user":
                holder["_last_question"] = _msg_text(m.get("content", ""))[:60]
                break
        return (
            session.chat_messages,
            gr.update(value="", placeholder=t("conversation_active")),
            gr.update(value=f"💬 {t('session_resumed')} — {t('status_default')}"),
        )

    if app is not None:
        app.load(fn=_auto_resume_on_load, inputs=[lang_state],
                 outputs=[chatbot, user_input, status_box])
        app.load(fn=None, js=_sidebar_fix_js)
        app.load(fn=None, js=_hint_delegate_js)
        app.load(fn=None, js=_tab_fill_js)
