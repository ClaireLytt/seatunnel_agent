"""Event/result formatting helpers for the Text2SQL UI."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from .chat_history import list_t2s_sessions
from .favorites import FavoritesStore
from .i18n import HINTS_I18N, TOOL_EMOJI, TOOL_LABEL_I18N
from .i18n import t2s as _t2s
from .qlog import QueryLogger
from .schema import SchemaStore
from .ui_cards import (
    _esc_html,
    _md_table,
    build_diff_card,
    build_lineage_card,
    build_quality_card,
    build_review_card,
)

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

def _format_tool_result(name: str, raw: str, lang: str = "en",
                        store: SchemaStore | None = None) -> str:
    from .formatter import format_sql
    from .lineage import trace_lineage

    t = lambda k: _t2s(lang, k)
    labels = TOOL_LABEL_I18N.get(lang, TOOL_LABEL_I18N["en"])
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"\U0001f4e6 **{name}**\n```\n{str(raw)[:500]}\n```"

    label = labels.get(name, name)

    if data.get("error"):
        return f"❌ **{label} {t('failed')}**\n\n{_esc_html(str(data['error'])[:500])}"

    if name == "match_tables":
        lines = [f"\U0001f50d **{t('candidates')}** ({data.get('count', 0)}):", ""]
        for c in data.get("candidates", []):
            cols = _esc_html(", ".join(c.get("matched_columns", [])[:5]))
            lines.append(
                f"- **`{c['table']}`** — {_esc_html(str(c.get('comment', '')))} "
                f"({t('score')} {c.get('score', 0)}, {t('type')} {_esc_html(str(c.get('table_type', '?')))})"
                + (f", {t('matched_cols')}: {cols}" if cols else "")
            )
        return "\n".join(lines)

    if name == "get_table_schema":
        cols = data.get("columns", [])
        parts = [
            f"\U0001f4d6 **`{data.get('table', '?')}`** — {_esc_html(str(data.get('comment', '')))}",
            f"{t('table_type')}: {_esc_html(str(data.get('table_type', '?')))} · {t('cols_count')}: {len(cols)}"
            + (f" · {t('partitioned')}" if data.get("partitioned") else ""),
        ]
        if data.get("partition_columns"):
            pc = ", ".join(
                f"`{p['name']}`({_esc_html(str(p.get('comment', '')))})"
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
        if sql:
            try:
                with _shared_holder_lock:
                    ds_type = _shared_holder.get("ds_type", "hive")
                card = build_review_card(sql, ds_type, store, lang)
                if card:
                    lines.append("")
                    lines.append(card)
            except Exception:
                pass
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
                hint = _esc_html(str(ev.get("retry_hint", "")))
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


def _session_choices_global() -> list[str]:
    sessions = list_t2s_sessions()
    return [f"{s['title']} ({s['updated_at'][:10]}) [{s['id']}]" for s in sessions]




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



def _placeholder(lang: str = "en") -> str:
    hints = HINTS_I18N.get(lang, HINTS_I18N["en"])
    cards = "\n".join(f'<div class="st-hint-card">{h}</div>' for h in hints)
    title = _t2s(lang, "placeholder_title")
    return f'''<div class="st-empty-state">
  <div class="st-empty-logo" style="background:#0ea5e9;">SQL</div>
  <div class="st-empty-title">{title}</div>
  <div class="st-empty-hints">{cards}</div>
</div>'''

