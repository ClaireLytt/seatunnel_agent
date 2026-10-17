"""Module-level HTML card builders for the Data Comparison UI.

Gradio-free by design: pure functions returning HTML strings, safe to import
from a REST layer (verified -- no ``gradio`` import here).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from seatunnel_agent.agents.data.text2sql.differ import ResultDiff
from seatunnel_agent.common.bridge import DATASKEW_SQL_KEY

from .comparator import (
    GINI_SKEW_THRESHOLD,
    AggregateResult,
    BatchFullItem,
    CompareReport,
    KeyedDiffResult,
    ProfileResult,
    QualityResult,
    ReportDiff,
    RowCountResult,
    SchemaDiffResult,
    SkewResult,
    ThresholdConfig,
    TrendAlert,
    check_row_count_threshold,
    skew_side_verdict,
)
from .i18n import dc
from .ui_shared import (
    _DELTA_WARN_PCT,
    _LIST_LIMIT,
    _TD,
    _TH,
    _details_card,
    _esc_html,
)

# ---------------------------------------------------------------------------
# HTML card builders
# ---------------------------------------------------------------------------

def build_schema_diff_card(result: SchemaDiffResult, lang: str = "en") -> str:
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not result.has_changes:
        return (
            '<div style="border:1px solid #bbf7d0;border-radius:8px;padding:12px;'
            'background:#f0fdf4;margin-bottom:8px;">'
            f'<b style="color:#16a34a;">{t("dc_schema_result")}</b> — '
            f'{t("dc_identical")}</div>'
        )

    th = 'style="padding:4px 10px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;"'
    td = 'style="padding:4px 10px;font-size:12px;border-bottom:1px solid #f3f4f6;"'
    rows_html = ""
    for item in result.items:
        if item.status == "removed":
            color = "#fef2f2"
            badge = f'<span style="color:#dc2626;font-weight:600;">{t("dc_removed")}</span>'
        elif item.status == "added":
            color = "#f0fdf4"
            badge = f'<span style="color:#16a34a;font-weight:600;">{t("dc_added")}</span>'
        else:
            color = "#fffbeb"
            badge = f'<span style="color:#d97706;font-weight:600;">{t("dc_type_changed")}</span>'
        rows_html += (
            f'<tr style="background:{color};">'
            f'<td {td}>{esc(item.column)}</td>'
            f'<td {td}>{esc(item.type_a)}</td>'
            f'<td {td}>{esc(item.type_b)}</td>'
            f'<td {td}>{badge}</td></tr>'
        )

    summary = []
    if result.cols_only_a:
        summary.append(f'<span style="color:#dc2626;">{t("dc_removed")}: {result.cols_only_a}</span>')
    if result.cols_only_b:
        summary.append(f'<span style="color:#16a34a;">{t("dc_added")}: {result.cols_only_b}</span>')
    if result.type_changes:
        summary.append(f'<span style="color:#d97706;">{t("dc_type_changed")}: {result.type_changes}</span>')

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#4338ca;cursor:pointer;">'
        f'{t("dc_schema_result")} — {" · ".join(summary)}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_column")}</th><th {th}>{t("dc_type_a")}</th>'
        f'<th {th}>{t("dc_type_b")}</th><th {th}>{t("dc_status")}</th></tr>'
        f'{rows_html}</table></details>'
    )


def _threshold_badge(passed: bool, lang: str) -> str:
    if passed:
        return (' <span style="background:#16a34a;color:#fff;padding:2px 8px;'
                f'border-radius:4px;font-size:11px;margin-left:8px;">'
                f'{dc(lang, "dc_threshold_pass")}</span>')
    return (' <span style="background:#dc2626;color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:11px;margin-left:8px;">'
            f'{dc(lang, "dc_threshold_fail")}</span>')


def build_count_card(
    result: RowCountResult, lang: str = "en",
    threshold: ThresholdConfig | None = None,
) -> str:
    t = lambda k: dc(lang, k)

    if result.delta == 0:
        border = "#bbf7d0"
        bg = "#f0fdf4"
        badge = f'<span style="color:#16a34a;font-weight:600;">{t("dc_match")}</span>'
    elif abs(result.delta_pct) < _DELTA_WARN_PCT:
        border = "#fde68a"
        bg = "#fffbeb"
        badge = f'<span style="color:#d97706;font-weight:600;">{t("dc_delta")}: {result.delta:+d} ({result.delta_pct:+.1f}%)</span>'
    else:
        border = "#fecaca"
        bg = "#fef2f2"
        badge = f'<span style="color:#dc2626;font-weight:600;">{t("dc_delta")}: {result.delta:+d} ({result.delta_pct:+.1f}%)</span>'

    threshold_html = ""
    if threshold is not None:
        passed = check_row_count_threshold(result, threshold)
        threshold_html = _threshold_badge(passed, lang)

    return (
        f'<div style="border:1px solid {border};border-radius:8px;padding:12px;'
        f'background:{bg};margin-bottom:8px;">'
        f'<b style="color:#0369a1;">{t("dc_count_result")}</b>{threshold_html}<br>'
        f'{t("dc_count_a")}: <b>{result.count_a:,}</b> &nbsp; '
        f'{t("dc_count_b")}: <b>{result.count_b:,}</b> &nbsp; '
        f'{badge}</div>'
    )


def build_sql_result_card(diff, lang: str = "en", columns=None) -> str:
    """Card for custom-SQL result comparison.

    diff_results is key-less, so a changed row surfaces as one removed (A)
    plus one added (B) — unreadable for the aggregate-reconciliation SQL
    this feature exists for. Pair removed/added rows by their FIRST column
    (the natural group key) and render matched pairs as `A → B` per cell;
    genuinely unmatched rows stay in only-A / only-B sections."""
    t = lambda k: dc(lang, k)
    cols = list(columns or [])

    def _v(x) -> str:
        # tame float repr noise (108.19999999999999 -> 108.2) while keeping
        # deliberate long fractions (3000.1000001) visible
        if isinstance(x, float):
            return f"{x:.12g}"
        return str(x)

    removed = [tuple(r) for r in diff.removed_rows]
    added = [tuple(r) for r in diff.added_rows]

    by_key_b: dict = {}
    for r in added:
        by_key_b.setdefault(r[0] if r else None, []).append(r)
    pairs, only_a = [], []
    for r in removed:
        k = r[0] if r else None
        if by_key_b.get(k):
            pairs.append((r, by_key_b[k].pop(0)))
        else:
            only_a.append(r)
    only_b = [r for rows in by_key_b.values() for r in rows]

    if not pairs and not only_a and not only_b:
        badge = (f'<span style="color:#16a34a;font-weight:600;">'
                 f'✅ {t("dc_sqlres_match")}</span>')
        body = (f'<div style="color:#6b7280;font-size:12px;">'
                f'{diff.old_count} = {diff.new_count} rows</div>')
    else:
        badge = (f'<span style="color:#dc2626;font-weight:600;">'
                 f'{t("dc_sqlres_summary").format(changed=len(pairs), only_a=len(only_a), only_b=len(only_b))}</span>')
        th, td = _TH, _TD
        header = "".join(f"<th {th}>{_esc_html(str(c))}</th>" for c in cols)
        body = ""
        if pairs:
            rows_html = ""
            for ra, rb in pairs[:50]:
                cells = ""
                for i in range(max(len(ra), len(rb))):
                    va = ra[i] if i < len(ra) else None
                    vb = rb[i] if i < len(rb) else None
                    if i == 0 or str(va) == str(vb):
                        cells += f"<td {td}>{_esc_html(_v(va))}</td>"
                    else:
                        cells += (f'<td {td}><span style="color:#6b7280;">'
                                  f'{_esc_html(_v(va))}</span> → '
                                  f'<b style="color:#dc2626;">{_esc_html(_v(vb))}</b></td>')
                rows_html += f'<tr style="background:#fef2f2;">{cells}</tr>'
            body += (f'<div style="margin-top:6px;"><b style="color:#4f46e5;">'
                     f'{t("dc_sqlres_changed")} ({len(pairs)})</b>'
                     f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
                     f'<tr>{header}</tr>{rows_html}</table></div>')

        def _plain(title, rows, color):
            if not rows:
                return ""
            rows_html = "".join(
                "<tr>" + "".join(f"<td {td}>{_esc_html(_v(v))}</td>" for v in r) + "</tr>"
                for r in rows[:50])
            return (f'<div style="margin-top:8px;"><b style="color:{color};">'
                    f'{title} ({len(rows)})</b>'
                    f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
                    f'<tr>{header}</tr>{rows_html}</table></div>')

        body += _plain(t("dc_sqlres_only_a"), only_a, "#dc2626")
        body += _plain(t("dc_sqlres_only_b"), only_b, "#d97706")

    if any(re.fullmatch(r"_c\d+", str(c)) for c in cols):
        body += (f'<div style="color:#d97706;font-size:12px;margin-top:8px;">'
                 f'💡 {t("dc_sqlres_alias_hint")}</div>')

    return _details_card(
        f'<span style="color:#0891b2;">{t("dc_sqlres_title")} — {badge}</span>',
        body,
    )


def build_sample_diff_card(
    diff: ResultDiff, lang: str = "en", columns: list[str] | None = None,
) -> str:
    """Build HTML card for sample data diff, including actual row preview."""
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not diff.has_changes:
        return (
            '<div style="border:1px solid #bbf7d0;border-radius:8px;padding:12px;'
            'background:#f0fdf4;margin-bottom:8px;">'
            f'<b style="color:#0369a1;">{t("dc_sample_result")}</b> — '
            f'{t("dc_no_diff")}</div>'
        )

    parts: list[str] = []
    if diff.added_rows:
        parts.append(f'<span style="color:#16a34a;">{t("dc_added_rows")}: +{len(diff.added_rows)}</span>')
    if diff.removed_rows:
        parts.append(f'<span style="color:#dc2626;">{t("dc_removed_rows")}: -{len(diff.removed_rows)}</span>')
    if diff.columns_added:
        parts.append(f'<span style="color:#16a34a;">+cols: {", ".join(esc(c) for c in diff.columns_added[:5])}</span>')
    if diff.columns_removed:
        parts.append(f'<span style="color:#dc2626;">-cols: {", ".join(esc(c) for c in diff.columns_removed[:5])}</span>')

    header = (
        '<div style="border:1px solid #bae6fd;border-radius:8px;padding:12px;'
        'background:#f0f9ff;margin-bottom:8px;">'
        f'<b style="color:#0369a1;">{t("dc_sample_result")}</b><br>'
        f'{" · ".join(parts)}'
    )

    row_tables = ""
    th = 'style="padding:3px 8px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;"'
    td = 'style="padding:3px 8px;font-size:11px;border-bottom:1px solid #f3f4f6;"'

    preview_limit = 10
    cols = columns or []

    if diff.added_rows and cols:
        show = diff.added_rows[:preview_limit]
        row_tables += (
            f'<details style="margin-top:8px;"><summary style="font-size:12px;color:#16a34a;cursor:pointer;">'
            f'{t("dc_sample_preview")} — {t("dc_added_rows")} '
            f'({t("dc_showing_n_rows").format(n=len(show))})</summary>'
            f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
            f'<tr>{"".join(f"<th {th}>{esc(c)}</th>" for c in cols)}</tr>'
        )
        for row in show:
            cells = "".join(
                f'<td {td}>{esc(str(row[i]) if i < len(row) else "")}</td>'
                for i in range(len(cols))
            )
            row_tables += f'<tr style="background:#f0fdf4;">{cells}</tr>'
        row_tables += "</table></details>"

    if diff.removed_rows and cols:
        show = diff.removed_rows[:preview_limit]
        row_tables += (
            f'<details style="margin-top:8px;"><summary style="font-size:12px;color:#dc2626;cursor:pointer;">'
            f'{t("dc_sample_preview")} — {t("dc_removed_rows")} '
            f'({t("dc_showing_n_rows").format(n=len(show))})</summary>'
            f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
            f'<tr>{"".join(f"<th {th}>{esc(c)}</th>" for c in cols)}</tr>'
        )
        for row in show:
            cells = "".join(
                f'<td {td}>{esc(str(row[i]) if i < len(row) else "")}</td>'
                for i in range(len(cols))
            )
            row_tables += f'<tr style="background:#fef2f2;">{cells}</tr>'
        row_tables += "</table></details>"

    return header + row_tables + "</div>"


def build_aggregate_card(result: AggregateResult, lang: str = "en") -> str:
    t = lambda k: dc(lang, k)

    if not result.items:
        return (
            '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
            'background:#f9fafb;margin-bottom:8px;">'
            f'<b style="color:#6b7280;">{t("dc_agg_result")}</b> — '
            f'{t("dc_no_numeric")}</div>'
        )

    th = 'style="padding:4px 10px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;"'
    td = 'style="padding:4px 10px;font-size:12px;border-bottom:1px solid #f3f4f6;"'
    rows_html = ""
    for item in result.items:
        bg = "#fff" if item.match else "#fef2f2"
        badge = "" if item.match else f' <span style="color:#dc2626;font-size:10px;">({t("dc_mismatch")})</span>'
        va = _esc_html("NULL" if item.value_a is None else str(item.value_a))
        vb = _esc_html("NULL" if item.value_b is None else str(item.value_b))
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td {td}>{_esc_html(item.column)}</td>'
            f'<td {td}>{_esc_html(item.metric)}</td>'
            f'<td {td}>{va}</td><td {td}>{vb}</td>'
            f'<td {td}>{badge}</td></tr>'
        )

    summary_badge = (
        f'<span style="color:#dc2626;">{result.mismatches} {t("dc_mismatch")}</span>'
        if result.mismatches else
        f'<span style="color:#16a34a;">{t("dc_match")}</span>'
    )

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#7c3aed;cursor:pointer;">'
        f'{t("dc_agg_result")} — {summary_badge}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_column")}</th><th {th}>{t("dc_metric")}</th>'
        f'<th {th}>{t("dc_value_a")}</th><th {th}>{t("dc_value_b")}</th>'
        f'<th {th}></th></tr>'
        f'{rows_html}</table></details>'
    )


def build_batch_count_card(results: list[RowCountResult], lang: str = "en") -> str:
    """Build HTML card showing row counts for multiple table pairs."""
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not results:
        return (
            '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
            'background:#f9fafb;margin-bottom:8px;">'
            f'<b style="color:#6b7280;">{t("dc_batch_result")}</b> — '
            f'{t("dc_no_common")}</div>'
        )

    mismatches = sum(1 for r in results if r.delta != 0)
    summary = t("dc_common_tables").format(n=len(results))
    if mismatches:
        summary += f' · <span style="color:#dc2626;">{t("dc_diffs_found").format(n=mismatches)}</span>'
    else:
        summary += f' · <span style="color:#16a34a;">{t("dc_no_diffs")}</span>'

    th = 'style="padding:4px 10px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;"'
    td = 'style="padding:4px 10px;font-size:12px;border-bottom:1px solid #f3f4f6;"'
    rows_html = ""
    for r in results:
        if r.delta == 0:
            bg = "#f0fdf4"
            badge = f'<span style="color:#16a34a;">{t("dc_match")}</span>'
        else:
            bg = "#fef2f2"
            badge = f'<span style="color:#dc2626;">{r.delta:+d} ({r.delta_pct:+.1f}%)</span>'
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td {td}>{esc(r.table_a)}</td>'
            f'<td {td}>{r.count_a:,}</td>'
            f'<td {td}>{r.count_b:,}</td>'
            f'<td {td}>{badge}</td></tr>'
        )

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#0369a1;cursor:pointer;">'
        f'{t("dc_batch_result")} — {summary}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_table_name")}</th><th {th}>{t("dc_count_a")}</th>'
        f'<th {th}>{t("dc_count_b")}</th><th {th}>{t("dc_delta")}</th></tr>'
        f'{rows_html}</table></details>'
    )


def build_summary_card(report: CompareReport, lang: str = "en") -> str:
    """Build a summary card showing comparison overview."""
    t = lambda k: dc(lang, k)

    count = 0
    diffs = 0
    if report.schema is not None:
        count += 1
        if report.schema.has_changes:
            diffs += 1
    if report.row_count is not None:
        count += 1
        if report.row_count.delta != 0:
            diffs += 1
    if report.sample is not None:
        count += 1
        if report.sample.has_changes:
            diffs += 1
    if report.aggregate is not None:
        count += 1
        if report.aggregate.mismatches > 0:
            diffs += 1

    if diffs:
        border, bg = "#fde68a", "#fffbeb"
        diff_text = f'<span style="color:#d97706;font-weight:600;">{t("dc_diffs_found").format(n=diffs)}</span>'
    else:
        border, bg = "#bbf7d0", "#f0fdf4"
        diff_text = f'<span style="color:#16a34a;font-weight:600;">{t("dc_no_diffs")}</span>'

    elapsed = t("dc_elapsed").format(ms=report.elapsed_ms) if report.elapsed_ms else ""

    return (
        f'<div style="border:1px solid {border};border-radius:8px;padding:12px;'
        f'background:{bg};margin-bottom:10px;">'
        f'<b style="color:#1e40af;">{t("dc_summary")}</b> &nbsp; '
        f'{t("dc_comparisons_done").format(n=count)} · {diff_text}'
        f'{f" · {elapsed}" if elapsed else ""}</div>'
    )


# ---------------------------------------------------------------------------
# New card builders  (A — keyed diff, C — profile)
# ---------------------------------------------------------------------------

def build_keyed_diff_card(result: KeyedDiffResult, lang: str = "en") -> str:
    """Build HTML card for key-based row diff."""
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not result.added and not result.removed and not result.modified:
        return (
            '<div style="border:1px solid #bbf7d0;border-radius:8px;padding:12px;'
            'background:#f0fdf4;margin-bottom:8px;">'
            f'<b style="color:#0369a1;">{t("dc_key_diff")}</b> — '
            f'{t("dc_no_diff")}</div>'
        )

    parts: list[str] = []
    if result.added:
        parts.append(f'<span style="color:#16a34a;">{t("dc_added_rows")}: +{len(result.added)}</span>')
    if result.removed:
        parts.append(f'<span style="color:#dc2626;">{t("dc_removed_rows")}: -{len(result.removed)}</span>')
    if result.modified:
        parts.append(f'<span style="color:#d97706;">{t("dc_modified_rows")}: {len(result.modified)}</span>')

    html = (
        '<div style="border:1px solid #e0e7ff;border-radius:8px;padding:12px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<b style="color:#0369a1;">{t("dc_key_diff")}</b> '
        f'(key: {esc(", ".join(result.key_columns))})<br>'
        f'{" · ".join(parts)}'
    )

    th = 'style="padding:3px 8px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;"'
    td = 'style="padding:3px 8px;font-size:11px;border-bottom:1px solid #f3f4f6;"'

    if result.modified:
        html += (
            f'<details style="margin-top:8px;" open><summary style="font-size:12px;color:#d97706;cursor:pointer;">'
            f'{t("dc_modified_rows")} ({len(result.modified)})</summary>'
            f'<table style="width:100%;border-collapse:collapse;margin-top:4px;">'
            f'<tr><th {th}>Key</th><th {th}>{t("dc_column")}</th>'
            f'<th {th}>{t("dc_old_val")}</th><th {th}>{t("dc_new_val")}</th></tr>'
        )
        for mr in result.modified[:_LIST_LIMIT]:
            key_str = esc(str(mr.key))
            for col, old_v, new_v in mr.changes:
                html += (
                    f'<tr style="background:#fffbeb;">'
                    f'<td {td}>{key_str}</td><td {td}>{esc(col)}</td>'
                    f'<td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #f3f4f6;color:#dc2626;">{esc(str(old_v))}</td>'
                    f'<td style="padding:3px 8px;font-size:11px;border-bottom:1px solid #f3f4f6;color:#16a34a;">{esc(str(new_v))}</td></tr>'
                )
        html += "</table></details>"

    # Feature F — drill-down per modified row
    if result.modified:
        for mr in result.modified[:_LIST_LIMIT]:
            if mr.row_a is not None or mr.row_b is not None:
                key_str = _esc_html(str(mr.key))
                detail_td = 'style="padding:2px 6px;font-size:10px;border-bottom:1px solid #f3f4f6;"'
                row_a_vals = mr.row_a if mr.row_a else ()
                row_b_vals = mr.row_b if mr.row_b else ()
                html += (
                    f'<details style="margin-left:16px;margin-top:2px;">'
                    f'<summary style="font-size:11px;color:#6b7280;cursor:pointer;">'
                    f'{dc(lang, "dc_drill_down")} — Key: {key_str}</summary>'
                    f'<div style="display:flex;gap:12px;margin-top:4px;">'
                )
                if row_a_vals:
                    html += (
                        f'<div><b style="font-size:10px;">{dc(lang, "dc_row_values_a")}</b>'
                        f'<table style="border-collapse:collapse;">'
                    )
                    for v in row_a_vals:
                        html += f'<tr><td {detail_td}>{esc(str(v))}</td></tr>'
                    html += '</table></div>'
                if row_b_vals:
                    html += (
                        f'<div><b style="font-size:10px;">{dc(lang, "dc_row_values_b")}</b>'
                        f'<table style="border-collapse:collapse;">'
                    )
                    for v in row_b_vals:
                        html += f'<tr><td {detail_td}>{esc(str(v))}</td></tr>'
                    html += '</table></div>'
                html += '</div></details>'

    html += "</div>"
    return html


def build_quality_card(results: list[QualityResult], lang: str = "en",
                       side_label: str = "") -> str:
    """Build HTML card for quality rule check results (one card per side)."""
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not results:
        return ""

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    th = 'style="padding:4px 10px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;"'
    td = 'style="padding:4px 10px;font-size:12px;border-bottom:1px solid #f3f4f6;"'
    rows_html = ""
    for r in results:
        bg = "#f0fdf4" if r.passed else "#fef2f2"
        badge = (f'<span style="color:#16a34a;">{t("dc_quality_pass")}</span>'
                 if r.passed else
                 f'<span style="color:#dc2626;">{t("dc_quality_fail")}</span>')
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td {td}>{esc(r.rule.column)}</td>'
            f'<td {td}>{esc(r.rule.rule_type)}</td>'
            f'<td {td}>{r.actual_value:.2f}</td>'
            f'<td {td}>{badge}</td></tr>'
        )

    summary = (f'<span style="color:#16a34a;">{passed} {t("dc_quality_pass")}</span>'
               f' / <span style="color:#dc2626;">{failed} {t("dc_quality_fail")}</span>')

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#0891b2;cursor:pointer;">'
        f'{t("dc_quality_result")}'
        f'{f" ({side_label})" if side_label else ""} — {summary}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_column")}</th><th {th}>Rule</th>'
        f'<th {th}>Actual</th><th {th}>{t("dc_status")}</th></tr>'
        f'{rows_html}</table></details>'
    )


def build_diff_sql_card(sql: str, lang: str = "en") -> str:
    """Build HTML card showing generated diff SQL."""
    t = lambda k: dc(lang, k)
    if not sql.strip():
        return (
            '<div style="border:1px solid #bbf7d0;border-radius:8px;padding:12px;'
            'background:#f0fdf4;margin-bottom:8px;">'
            f'<b style="color:#0369a1;">{t("dc_diff_sql_result")}</b> — '
            f'{t("dc_diff_sql_no_diff")}</div>'
        )
    return (
        f'<div style="border:1px solid #e0e7ff;border-radius:8px;padding:12px;'
        f'background:#f8fafc;margin-bottom:8px;">'
        f'<b style="color:#0369a1;">{t("dc_diff_sql_result")}</b>'
        f'<pre style="background:#1e293b;color:#e2e8f0;padding:16px;border-radius:8px;'
        f'overflow-x:auto;font-size:12px;margin-top:8px;white-space:pre-wrap;">'
        f'{_esc_html(sql)}</pre></div>'
    )


def build_profile_card(result: ProfileResult, lang: str = "en") -> str:
    """Build HTML card for column profile comparison."""
    t = lambda k: dc(lang, k)
    esc = _esc_html

    if not result.items:
        return (
            '<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
            'background:#f9fafb;margin-bottom:8px;">'
            f'<b style="color:#6b7280;">{t("dc_profile_result")}</b></div>'
        )

    th = 'style="padding:4px 8px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;"'
    td = 'style="padding:4px 8px;font-size:11px;border-bottom:1px solid #f3f4f6;"'

    rows_html = ""
    for item in result.items:
        dist_match = item.distinct_a == item.distinct_b
        null_match = abs(item.null_rate_a - item.null_rate_b) < 0.1
        bg = "#fff" if (dist_match and null_match) else "#fffbeb"
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td {td}>{esc(item.column)}</td>'
            f'<td {td}>{item.distinct_a:,}</td><td {td}>{item.distinct_b:,}</td>'
            f'<td {td}>{item.null_rate_a:.1f}%</td><td {td}>{item.null_rate_b:.1f}%</td>'
            f'<td {td}>{esc(str(item.min_a) if item.min_a is not None else "")}</td>'
            f'<td {td}>{esc(str(item.min_b) if item.min_b is not None else "")}</td>'
            f'<td {td}>{esc(str(item.max_a) if item.max_a is not None else "")}</td>'
            f'<td {td}>{esc(str(item.max_b) if item.max_b is not None else "")}</td></tr>'
        )

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#0891b2;cursor:pointer;">'
        f'{t("dc_profile_result")} — {result.total_a:,} / {result.total_b:,} rows</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_column")}</th>'
        f'<th {th}>{t("dc_distinct")} A</th><th {th}>{t("dc_distinct")} B</th>'
        f'<th {th}>{t("dc_null_rate")} A</th><th {th}>{t("dc_null_rate")} B</th>'
        f'<th {th}>{t("dc_min")} A</th><th {th}>{t("dc_min")} B</th>'
        f'<th {th}>{t("dc_max")} A</th><th {th}>{t("dc_max")} B</th></tr>'
        f'{rows_html}</table></details>'
    )


def build_skew_card(result: SkewResult, lang: str = "en",
                    conn_b=None) -> str:
    """Build HTML card for data skew analysis.

    *conn_b* is side B's ``DatabaseConfig`` (or None, e.g. when rendering a
    saved report): with it, the goto-dataskew button also hands the
    connection over via a short-lived cookie — no password travels."""
    t = lambda k: dc(lang, k)
    esc = _esc_html
    if not result.items:
        return (
            '<div style="padding:10px;color:#6b7280;background:#f9fafb;'
            f'border-radius:8px;margin-bottom:8px;">{t("dc_skew_result")}</div>'
        )
    th = _TH
    td = _TD

    # Side-vs-side qualification: sync-pipeline symptom vs business fact
    verdict, v_cols = skew_side_verdict(result)
    verdict_html = ""
    if verdict != "ok":
        style = ("color:#dc2626;background:#fef2f2;" if verdict == "mismatch"
                 else "color:#b45309;background:#fffbeb;")
        key = ("dc_skew_verdict_mismatch" if verdict == "mismatch"
               else "dc_skew_verdict_both")
        cols = ", ".join(f"<b>{esc(c)}</b>" for c in v_cols[:5])
        goto_html = ""
        if verdict == "both_skewed" and v_cols:
            # Hand a hot-key GROUP BY over to /dataskew via the same
            # localStorage bridge the SQL-review page uses: the group key
            # becomes a probe target there, so 验证倾斜 measures it and the
            # rewrite templates / engine params come pre-filled.
            col = v_cols[0]
            handoff_sql = (
                f"-- from Data Comparison: `{result.table_b}`.`{col}` skewed "
                f"on both sides\n"
                f"SELECT {col}, COUNT(*) AS cnt\n"
                f"FROM {result.table_b}\n"
                f"GROUP BY {col}\n"
                f"ORDER BY cnt DESC\nLIMIT 100;"
            )
            conn_js = ""
            if conn_b is not None:
                # side B connection minus the password, as a 3-minute
                # cookie the /dataskew page reads on load (gr.Request)
                payload = json.dumps({
                    "ds_type": str(getattr(conn_b, "ds_type", "") or ""),
                    "host": str(getattr(conn_b, "host", "") or ""),
                    "port": str(getattr(conn_b, "port", "") or ""),
                    "database": str(getattr(conn_b, "database", "") or ""),
                    "username": str(getattr(conn_b, "username", "") or ""),
                }, ensure_ascii=False)
                conn_js = (
                    "document.cookie = 'st_dataskew_conn=' + "
                    "encodeURIComponent(" + json.dumps(payload)
                    + ") + '; path=/; max-age=180';"
                )
            onclick = esc(
                f"localStorage.setItem('{DATASKEW_SQL_KEY}', "
                + json.dumps(handoff_sql, ensure_ascii=False)
                + "); " + conn_js + " window.open('/dataskew', '_blank');"
            )
            goto_html = (
                f' <button onclick="{onclick}" style="margin-left:8px;'
                'padding:1px 8px;font-size:11px;color:#0d9488;'
                'background:#f0fdfa;border:1px solid #99f6e4;'
                'border-radius:4px;cursor:pointer;">'
                + t("dc_skew_goto_dataskew") + "</button>"
            )
        verdict_html = (
            f'<div style="{style}border-radius:6px;padding:6px 10px;'
            f'margin-top:8px;font-size:12px;">'
            + t(key).format(cols=cols) + goto_html + "</div>"
        )

    items_html = ""
    for item in result.items:
        warn_a = ' style="color:#dc2626;font-weight:600;"' if item.gini_a > GINI_SKEW_THRESHOLD else ""
        warn_b = ' style="color:#dc2626;font-weight:600;"' if item.gini_b > GINI_SKEW_THRESHOLD else ""
        items_html += (
            f'<tr style="background:#f0fdfa;">'
            f'<td {td}><b>{esc(item.column)}</b></td>'
            f'<td {td}{warn_a}>{item.gini_a}</td><td {td}{warn_b}>{item.gini_b}</td>'
            f'<td {td}>{item.cv_a}</td><td {td}>{item.cv_b}</td>'
            f'<td {td}>{item.top1_pct_a}%</td><td {td}>{item.top1_pct_b}%</td>'
            f'<td {td}>{item.ndv_a}</td><td {td}>{item.ndv_b}</td></tr>'
        )
        for bkt in item.buckets:
            items_html += (
                f'<tr><td {td} style="padding-left:20px;font-size:10px;">'
                f'{esc(bkt.value)}</td>'
                f'<td {td} colspan="2" style="font-size:10px;">'
                f'{bkt.count_a:,} ({bkt.pct_a}%)</td>'
                f'<td {td} colspan="2" style="font-size:10px;">'
                f'{bkt.count_b:,} ({bkt.pct_b}%)</td>'
                f'<td {td} colspan="4"></td></tr>'
            )

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#0d9488;cursor:pointer;">'
        f'{t("dc_skew_result")} — {result.total_a:,} / {result.total_b:,} rows</summary>'
        f'{verdict_html}'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_skew_column")}</th>'
        f'<th {th}>{t("dc_skew_gini")} A</th><th {th}>{t("dc_skew_gini")} B</th>'
        f'<th {th}>{t("dc_skew_cv")} A</th><th {th}>{t("dc_skew_cv")} B</th>'
        f'<th {th}>{t("dc_skew_top1")} A</th><th {th}>{t("dc_skew_top1")} B</th>'
        f'<th {th}>{t("dc_skew_ndv")} A</th><th {th}>{t("dc_skew_ndv")} B</th></tr>'
        f'{items_html}</table></details>'
    )


def build_checksum_card(result, lang: str = "en") -> str:
    """Build HTML card for checksum comparison."""
    t = lambda k: dc(lang, k)
    if not result.items:
        return (
            '<div style="padding:10px;color:#6b7280;background:#f9fafb;'
            f'border-radius:8px;margin-bottom:8px;">{t("dc_checksum_result")}</div>'
        )
    if result.mismatch_count == 0:
        badge = f'<span style="color:#16a34a;font-weight:600;">✅ {t("dc_checksum_all_match")}</span>'
    else:
        badge = (f'<span style="color:#dc2626;font-weight:600;">'
                 f'{result.mismatch_count} {t("dc_checksum_mismatch")}</span>')

    th = _TH
    td = _TD
    rows_html = ""
    for item in result.items:
        color = "#f0fdf4" if item.match else "#fef2f2"
        status = t("dc_checksum_match") if item.match else t("dc_checksum_mismatch")
        rows_html += (
            f'<tr style="background:{color};">'
            f'<td {td}>{_esc_html(str(item.segment))}</td>'
            f'<td {td}>{_esc_html(item.checksum_a[:16])}</td>'
            f'<td {td}>{_esc_html(item.checksum_b[:16])}</td>'
            f'<td {td}>{status}</td></tr>'
        )
    table_html = (
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_checksum_segment")}</th>'
        f'<th {th}>Checksum A</th><th {th}>Checksum B</th>'
        f'<th {th}>Status</th></tr>'
        f'{rows_html}</table>'
    )
    return _details_card(
        f'<span style="color:#4f46e5;">{t("dc_checksum_result")} — {badge}</span>',
        table_html,
    )


def build_chunked_card(result, lang: str = "en") -> str:
    """Build HTML card for chunked (blocked) verification."""
    t = lambda k: dc(lang, k)
    summary = t("dc_chunked_summary").format(
        chunks=result.chunk_count, mismatched=len(result.mismatched),
        ta=result.total_a, tb=result.total_b)
    if result.match:
        badge = (f'<span style="color:#16a34a;font-weight:600;">'
                 f'✅ {t("dc_chunked_all_match")}</span>')
    else:
        badge = (f'<span style="color:#dc2626;font-weight:600;">'
                 f'{len(result.mismatched)} {t("dc_checksum_mismatch")}</span>')

    body = f'<div style="color:#6b7280;font-size:12px;">{_esc_html(summary)}</div>'
    if result.note:
        body += (f'<div style="color:#d97706;font-size:12px;margin-top:4px;">'
                 f'{_esc_html(result.note)}</div>')

    def _keys(label: str, keys: list, color: str) -> str:
        if not keys:
            return ""
        shown = ", ".join(_esc_html(str(k)) for k in keys[:50])
        more = f" … (+{len(keys) - 50})" if len(keys) > 50 else ""
        return (f'<div style="margin-top:6px;"><b style="color:{color};">'
                f'{label} ({len(keys)})</b>: '
                f'<span style="font-family:monospace;font-size:12px;">'
                f'{shown}{more}</span></div>')

    body += _keys(t("dc_chunked_only_a"), result.only_a, "#dc2626")
    body += _keys(t("dc_chunked_only_b"), result.only_b, "#d97706")
    body += _keys(t("dc_chunked_changed"), result.changed, "#4f46e5")
    if result.drill_truncated:
        body += (f'<div style="color:#d97706;font-size:12px;margin-top:6px;">'
                 f'⚠️ {t("dc_chunked_truncated")}</div>')

    if result.mismatched:
        th, td = _TH, _TD
        rows_html = ""
        for cm in result.mismatched[:50]:
            rows_html += (
                f'<tr style="background:#fef2f2;">'
                f'<td {td}>{cm.chunk_id}</td>'
                f'<td {td}>[{cm.pk_lo:g}, {cm.pk_hi:g})</td>'
                f'<td {td}>{cm.count_a}</td><td {td}>{cm.count_b}</td></tr>')
        body += (
            f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
            f'<tr><th {th}>Chunk</th><th {th}>PK Range</th>'
            f'<th {th}>Rows A</th><th {th}>Rows B</th></tr>'
            f'{rows_html}</table>')

    return _details_card(
        f'<span style="color:#0891b2;">{t("dc_chunked_result")} — {badge}</span>',
        body,
    )


def build_partition_card(result, lang: str = "en") -> str:
    """Build HTML card for partition-level comparison."""
    t = lambda k: dc(lang, k)
    if not result.items:
        return (
            '<div style="padding:10px;color:#6b7280;background:#f9fafb;'
            f'border-radius:8px;margin-bottom:8px;">{t("dc_partition_result")}</div>'
        )
    th = _TH
    td = _TD
    rows_html = ""
    for item in result.items:
        color = "#f0fdf4" if item.delta == 0 else "#fef2f2"
        rows_html += (
            f'<tr style="background:{color};">'
            f'<td {td}>{_esc_html(item.partition_value)}</td>'
            f'<td {td}>{item.count_a:,}</td>'
            f'<td {td}>{item.count_b:,}</td>'
            f'<td {td}>{item.delta:+,}</td>'
            f'<td {td}>{item.delta_pct:+.1f}%</td></tr>'
        )
    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#7c3aed;cursor:pointer;">'
        f'{t("dc_partition_result")} — {t("dc_partition_total_delta")}: {result.total_delta:,}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_partition_value")}</th>'
        f'<th {th}>Count A</th><th {th}>Count B</th>'
        f'<th {th}>{t("dc_partition_delta")}</th><th {th}>%</th></tr>'
        f'{rows_html}</table></details>'
    )


def build_custom_agg_card(result, lang: str = "en") -> str:
    """Build HTML card for custom aggregate comparison."""
    t = lambda k: dc(lang, k)
    if not result.items:
        return (
            '<div style="padding:10px;color:#6b7280;background:#f9fafb;'
            f'border-radius:8px;margin-bottom:8px;">{t("dc_custom_agg_result")}</div>'
        )
    th = _TH
    td = _TD
    rows_html = ""
    for item in result.items:
        color = "#f0fdf4" if item.match else "#fef2f2"
        rows_html += (
            f'<tr style="background:{color};">'
            f'<td {td}>{_esc_html(item.alias)}</td>'
            f'<td {td}>{_esc_html(item.expression)}</td>'
            f'<td {td}>{_esc_html(str(item.value_a))}</td>'
            f'<td {td}>{_esc_html(str(item.value_b))}</td>'
            f'<td {td}>{"✓" if item.match else "✗"}</td></tr>'
        )
    mismatch_badge = ""
    if result.mismatches > 0:
        mismatch_badge = f' — <span style="color:#dc2626;">{result.mismatches} mismatch</span>'
    table_html = (
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_custom_agg_alias")}</th>'
        f'<th {th}>{t("dc_custom_agg_expression")}</th>'
        f'<th {th}>A</th><th {th}>B</th><th {th}>Match</th></tr>'
        f'{rows_html}</table>'
    )
    return _details_card(
        f'<span style="color:#ea580c;">{t("dc_custom_agg_result")}{mismatch_badge}</span>',
        table_html,
    )


def build_batch_template_card(results: list[dict], lang: str = "en") -> str:
    """Build HTML card showing batch template run results."""
    t = lambda k: dc(lang, k)
    if not results:
        return ""
    th = _TH
    td = _TD
    rows = ""
    pass_n = sum(1 for r in results if r["status"] == "pass")
    fail_n = len(results) - pass_n
    for r in results:
        color = "#f0fdf4" if r["status"] == "pass" else "#fef2f2"
        status_text = t("dc_batch_templates_pass") if r["status"] == "pass" else t("dc_batch_templates_fail")
        detail = r.get("detail", "")
        cnt_info = ""
        if "count_a" in r:
            cnt_info = f'{r["count_a"]} / {r["count_b"]}'
        sc = r.get("schema_changes", "")
        am = r.get("agg_mismatches", "")
        rows += (
            f'<tr style="background:{color};">'
            f'<td {td}>{_esc_html(r["name"])}</td>'
            f'<td {td}>{_esc_html(r.get("table_a", ""))}</td>'
            f'<td {td}>{_esc_html(r.get("table_b", ""))}</td>'
            f'<td {td}>{cnt_info}</td>'
            f'<td {td}>{sc}</td>'
            f'<td {td}>{am}</td>'
            f'<td {td}><b>{status_text}</b></td>'
            f'<td {td}>{_esc_html(detail)}</td></tr>'
        )
    summary = dc(lang, "dc_batch_summary").format(total=len(results), pass_n=pass_n, fail_n=fail_n)
    return (
        '<details open style="border:1px solid #c7d2fe;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#6366f1;cursor:pointer;">'
        f'{t("dc_batch_templates_result")} — {summary}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>Template</th><th {th}>Table A</th><th {th}>Table B</th>'
        f'<th {th}>Counts</th><th {th}>{t("dc_batch_tpl_schema")}</th>'
        f'<th {th}>{t("dc_batch_tpl_agg")}</th>'
        f'<th {th}>Status</th><th {th}>Detail</th></tr>'
        f'{rows}</table></details>'
    )


def build_trend_alert_card(alerts: list[TrendAlert], lang: str = "en") -> str:
    """Build HTML card showing trend alert results."""
    t = lambda k: dc(lang, k)
    if not alerts:
        return ""
    th = _TH
    td = _TD
    rows = ""
    for a in alerts:
        color = "#fef2f2" if a.triggered else "#f0fdf4"
        status = t("dc_alert_triggered") if a.triggered else t("dc_alert_ok")
        rows += (
            f'<tr style="background:{color};">'
            f'<td {td}>{_esc_html(a.metric)}</td>'
            f'<td {td}>{a.threshold}</td>'
            f'<td {td}>{a.consecutive_actual}/{a.consecutive_required}</td>'
            f'<td {td}>{a.current_value}</td>'
            f'<td {td}><b>{status}</b></td></tr>'
        )
    return (
        '<details open style="border:1px solid #fde68a;border-radius:8px;padding:10px;'
        'background:#fffbeb;margin-bottom:8px;margin-top:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#d97706;cursor:pointer;">'
        f'{t("dc_alert_result")}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_alert_metric")}</th>'
        f'<th {th}>{t("dc_alert_threshold")}</th>'
        f'<th {th}>{t("dc_alert_consecutive")}</th>'
        f'<th {th}>Value</th><th {th}>Status</th></tr>'
        f'{rows}</table></details>'
    )


def build_report_diff_card(rdiff: ReportDiff, lang: str = "en") -> str:
    t = lambda k: dc(lang, k)
    if not rdiff.has_changes:
        return (
            f'<div style="border:1px solid #86efac;border-radius:8px;padding:12px;'
            f'background:#f0fdf4;margin-bottom:8px;">'
            f'<b style="color:#16a34a;">{t("dc_report_diff_no_change")}</b></div>'
        )
    th = _TH
    td = _TD
    rows = ""
    for item in rdiff.items:
        if not item.changed:
            continue
        rows += (
            f'<tr><td {td}>{_esc_html(item.section)}</td>'
            f'<td {td}>{_esc_html(item.field)}</td>'
            f'<td {td}>{item.old_value}</td>'
            f'<td {td}>{item.new_value}</td></tr>'
        )
    return (
        '<details open style="border:1px solid #c7d2fe;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#6366f1;cursor:pointer;">'
        f'{t("dc_report_diff_result")}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_report_diff_section")}</th>'
        f'<th {th}>{t("dc_report_diff_field")}</th>'
        f'<th {th}>{t("dc_report_diff_old_val")}</th>'
        f'<th {th}>{t("dc_report_diff_new_val")}</th></tr>'
        f'{rows}</table></details>'
    )


def build_lineage_card(table: str, upstream: list[str], lang: str = "en") -> str:
    t = lambda k: dc(lang, k)
    if not upstream:
        return (
            f'<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;'
            f'background:#f9fafb;margin-bottom:8px;">'
            f'<b>{t("dc_lineage_title")}</b>: {t("dc_lineage_no_deps")}</div>'
        )
    items_html = "".join(f"<li>{_esc_html(t)}</li>" for t in upstream)
    return (
        '<details open style="border:1px solid #c7d2fe;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#6366f1;cursor:pointer;">'
        f'{dc(lang, "dc_lineage_title")} — {_esc_html(table)}</summary>'
        f'<ul style="margin:8px 0;padding-left:20px;">{items_html}</ul></details>'
    )


# ---------------------------------------------------------------------------
# Standalone report page  (opens in new tab)
# ---------------------------------------------------------------------------

def build_standalone_report(report: CompareReport, lang: str = "en") -> str:
    """Build a full standalone HTML page for the comparison report."""
    t = lambda k: dc(lang, k)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cards: list[str] = []
    cards.append(build_summary_card(report, lang))
    if report.schema is not None:
        cards.append(build_schema_diff_card(report.schema, lang))
    if report.row_count is not None:
        cards.append(build_count_card(report.row_count, lang))
    if report.sample is not None:
        cards.append(build_sample_diff_card(report.sample, lang))
    if report.keyed_diff is not None:
        cards.append(build_keyed_diff_card(report.keyed_diff, lang))
    if report.aggregate is not None:
        cards.append(build_aggregate_card(report.aggregate, lang))
    if report.profile is not None:
        cards.append(build_profile_card(report.profile, lang))
    if report.skew is not None:
        cards.append(build_skew_card(report.skew, lang))
    if report.checksum is not None:
        cards.append(build_checksum_card(report.checksum, lang))
    if report.partition is not None:
        cards.append(build_partition_card(report.partition, lang))
    if report.custom_agg is not None:
        cards.append(build_custom_agg_card(report.custom_agg, lang))
    if report.chunked is not None:
        cards.append(build_chunked_card(report.chunked, lang))
    if report.batch_counts is not None:
        cards.append(build_batch_count_card(report.batch_counts, lang))

    body = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("dc_report_title")}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    max-width: 1100px; margin: 0 auto; padding: 24px 20px;
    background: #f8fafc; color: #1e293b; line-height: 1.5;
  }}
  .report-header {{
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 20px;
  }}
  .report-header h1 {{ font-size: 22px; margin: 0; color: #1e40af; }}
  .report-header .meta {{ font-size: 12px; color: #64748b; text-align: right; }}
  .print-btn {{
    padding: 6px 16px; background: #3b82f6; color: #fff; border: none;
    border-radius: 6px; cursor: pointer; font-size: 13px; margin-left: 12px;
  }}
  .print-btn:hover {{ background: #2563eb; }}
  table {{ font-size: 12px; }}
  details {{ margin-bottom: 10px; }}
  @media print {{
    .print-btn {{ display: none; }}
    body {{ background: #fff; padding: 10px; }}
    details {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="report-header">
  <div>
    <h1>{t("dc_report_title")}</h1>
    <div class="meta">{ts}</div>
  </div>
  <button class="print-btn" onclick="window.print()">{t("dc_print")}</button>
</div>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Batch full comparison card  (F)
# ---------------------------------------------------------------------------

def build_batch_full_card(
    items: list[BatchFullItem], lang: str = "en",
    threshold: ThresholdConfig | None = None,
) -> str:
    t = lambda k: dc(lang, k)
    esc = _esc_html

    passed = sum(1 for i in items if not i.has_diffs)
    failed = len(items) - passed

    summary = t("dc_batch_summary").format(
        pass_n=passed, fail_n=failed, total=len(items))

    th = 'style="padding:4px 10px;text-align:left;border-bottom:1px solid #e5e7eb;font-size:12px;"'
    td = 'style="padding:4px 10px;font-size:12px;border-bottom:1px solid #f3f4f6;"'

    rows_html = ""
    for item in items:
        bg = "#fef2f2" if item.has_diffs else "#f0fdf4"
        schema_ok = "✅" if (item.schema and not item.schema.has_changes) else "❌" if item.schema else "—"
        delta_str = f"{item.row_count.delta:+d}" if item.row_count else "—"
        agg_ok = "✅" if (item.aggregate and item.aggregate.mismatches == 0) else (
            f"❌ {item.aggregate.mismatches}" if item.aggregate else "—")
        status = '<span style="color:#16a34a;">✅</span>' if not item.has_diffs else (
            '<span style="color:#dc2626;">❌</span>')
        th_badge = ""
        if threshold and item.row_count:
            th_badge = _threshold_badge(check_row_count_threshold(item.row_count, threshold), lang)
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td {td}>{esc(item.table_a)}</td>'
            f'<td {td}>{schema_ok}</td>'
            f'<td {td}>{delta_str}{th_badge}</td>'
            f'<td {td}>{agg_ok}</td>'
            f'<td {td}>{status}</td></tr>'
        )

    return (
        '<details open style="border:1px solid #e0e7ff;border-radius:8px;padding:10px;'
        'background:#f8fafc;margin-bottom:8px;">'
        f'<summary style="font-weight:600;font-size:13px;color:#7c3aed;cursor:pointer;">'
        f'{t("dc_batch_full_result")} — {summary}</summary>'
        f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
        f'<tr><th {th}>{t("dc_table_name")}</th>'
        f'<th {th}>{t("dc_compare_schema")}</th>'
        f'<th {th}>{t("dc_delta")}</th>'
        f'<th {th}>{t("dc_compare_agg")}</th>'
        f'<th {th}>{t("dc_status")}</th></tr>'
        f'{rows_html}</table></details>'
    )

