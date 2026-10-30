"""HTML/markdown card builders for the Text2SQL UI (pure, no Gradio state)."""

from __future__ import annotations

import html
from typing import Any

from .i18n import t2s as _t2s
from .schema import SchemaStore


def _esc_html(s: str) -> str:
    # quote=False + manual &quot;: escape & < > " but keep ' intact —
    # several cards embed single-quoted JS in onclick attributes.
    return html.escape(str(s), quote=False).replace('"', "&quot;")


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
        from .join_advisor import suggest_joins
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
        f'{t("quality_title")} — {t("quality_warnings").format(n=len(warnings))}</summary>'
        f'<div style="font-size:12px;line-height:1.5;padding:4px;margin-top:4px;'
        f'border:1px solid #fde68a;border-radius:6px;background:#fffbeb;">{body}</div></details>'
    )


_MAX_REVIEW_URL_SQL = 1800  # keep the prefill URL well under browser limits


def _review_page_url(sql: str, dialect: str) -> str:
    from urllib.parse import quote
    encoded = quote(sql, safe="")
    if len(encoded) > _MAX_REVIEW_URL_SQL:
        return "/sqlreview"
    return f"/sqlreview?sql={encoded}&dialect={quote(dialect, safe='')}"


def build_review_card(sql: str, dialect: str, store: SchemaStore | None,
                      lang: str = "en") -> str:
    """Compact SQL-review card: static-lint the executed SQL and summarize.

    Links to /sqlreview for the full (LLM-assisted) review page.
    """
    from seatunnel_agent.agents.data.sql_review.agent import static_review_report
    from seatunnel_agent.agents.data.sql_review.i18n import catalog_label
    from seatunnel_agent.agents.data.sql_review.linter import normalize_dialect

    t = lambda k: _t2s(lang, k)
    esc = _esc_html
    dialect = normalize_dialect(dialect)
    rep = static_review_report(sql, dialect, store=store)
    if not rep.findings:
        return (
            f'<div style="margin-top:6px;font-size:11px;color:#10b981;">'
            f'✅ {t("review_card_pass")}</div>'
        )

    review_url = _review_page_url(sql, dialect)
    n_crit, n_risk = len(rep.criticals), len(rep.risks)
    n_sugg = len(rep.suggestions)
    counts = t("review_card_counts").format(c=n_crit, r=n_risk, s=n_sugg)
    header_color = "#dc2626" if n_crit else "#f59e0b" if n_risk else "#10b981"

    sev_label = {"critical": t("review_sev_critical"),
                 "risk": t("review_sev_risk"),
                 "suggestion": t("review_sev_suggestion")}
    sev_color = {"critical": "#dc2626", "risk": "#f59e0b",
                 "suggestion": "#10b981"}
    items: list[str] = []
    for f in rep.findings[:5]:
        sev = f.severity.value
        items.append(
            f'<div style="font-size:11px;padding:2px 0;">'
            f'<span style="display:inline-block;padding:0 5px;border-radius:3px;'
            f'font-size:9px;color:#fff;background:{sev_color.get(sev, "#6b7280")};'
            f'margin-right:4px;">{esc(sev_label.get(sev, sev))}</span>'
            f'<b>{esc(catalog_label(f.category, lang))}</b> — '
            f'{esc(f.description)}</div>'
        )
    if len(rep.findings) > 5:
        items.append(
            f'<div style="font-size:11px;padding:2px 0;color:#6b7280;">'
            f'… +{len(rep.findings) - 5}</div>'
        )
    items.append(
        f'<div style="font-size:11px;padding:4px 0 0;">'
        f'<a href="{review_url}" target="_blank" style="color:#0ea5e9;'
        f'text-decoration:none;">{t("review_card_more")}</a></div>'
    )
    body = "\n".join(items)
    return (
        f'<details style="margin-top:6px;">'
        f'<summary style="cursor:pointer;font-weight:600;font-size:12px;'
        f'color:{header_color};">\U0001f50d {t("review_card_title")} — {esc(counts)}</summary>'
        f'<div style="font-size:12px;line-height:1.5;padding:4px;margin-top:4px;'
        f'border:1px solid #e5e7eb;border-radius:6px;background:#f9fafb;">{body}</div></details>'
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


def _build_csv_data_uri(columns: list[str], rows: list) -> str:
    import base64 as _b64
    import csv as _csv
    import io as _io

    from .masking import apply_masking
    rows, _masked = apply_masking(columns, rows)
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(columns)
    w.writerows(rows)
    b64 = _b64.b64encode(buf.getvalue().encode("utf-8-sig")).decode("ascii")
    return f"data:text/csv;base64,{b64}"


_DL_BTN_STYLE = (
    "display:inline-flex;align-items:center;gap:4px;"
    "padding:4px 12px;margin:4px 4px 4px 0;"
    "border:1px solid var(--border-color-primary,#e0e0e0);"
    "border-radius:6px;background:var(--background-fill-secondary,#f7f7f7);"
    "color:var(--body-text-color,#333);font-size:13px;cursor:pointer;"
    "text-decoration:none;"
)
