# -*- coding: utf-8 -*-
"""Render GenResult as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .generator import GenResult
from .i18n import normalize_lang, tp


def render_markdown(result: GenResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    rows = len(result.tables[0].rows) if result.tables else 0
    lines = [f"## 🧪 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_dialect')} `{result.dialect}` · "
             + tp(lang, "rpt_stats").format(tables=len(result.tables),
                                            rows=rows),
             ""]
    if result.validation is not None:
        v = result.validation
        detail = {"ok": tp(lang, "val_ok").format(n=v.row_count),
                  "transpile_error": tp(lang, "val_transpile_error").format(
                      detail=v.detail),
                  "exec_error": tp(lang, "val_exec_error").format(
                      detail=v.detail),
                  "skipped": tp(lang, "val_skipped").format(detail=v.detail),
                  }.get(v.status, v.status)
        mark = "✅" if v.status == "ok" else "⚠️"
        lines.append(f"**{tp(lang, 'rpt_validation')}**: {mark} {detail}")
        if v.status == "ok" and v.row_count == 0:
            lines.append(tp(lang, "val_zero_rows"))
        lines.append("")
    for table in result.tables:
        ddl_cols = sum(1 for c in table.columns if c.source == "ddl")
        inf_cols = len(table.columns) - ddl_cols
        lines.append(f"### 📋 {tp(lang, 'rpt_table')} `{table.name}` "
                     f"({tp(lang, 'rpt_columns')} {len(table.columns)}: "
                     f"{tp(lang, 'rpt_from_ddl')} {ddl_cols} / "
                     f"{tp(lang, 'rpt_inferred')} {inf_cols})")
        lines.append(f"**{tp(lang, 'rpt_csv')}**")
        lines.append("```csv\n" + table.csv_text().rstrip() + "\n```")
        lines.append(f"<details><summary>{tp(lang, 'rpt_create')} / "
                     f"{tp(lang, 'rpt_insert')}</summary>\n")
        lines.append("```sql\n" + table.create_sql() + "\n\n"
                     + table.insert_sql() + "\n```\n</details>")
        lines.append("")
    if result.notes:
        lines.append(f"### ℹ️ {tp(lang, 'rpt_notes')}")
        lines.extend(f"- {n}" for n in result.notes)
        lines.append("")
    if result.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def result_to_dict(result: GenResult) -> dict[str, Any]:
    return result.to_dict()
