# -*- coding: utf-8 -*-
"""SyncResult → manifest dict / Markdown."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .core import SyncResult
from .i18n import SYNC_I18N, normalize_lang


def report_to_dict(result: SyncResult, lang: str = "zh") -> dict[str, Any]:
    plan = result.plan
    tables = []
    for t in result.tables:
        tables.append({
            "table": t.spec.full_name,
            "column_count": len(t.spec.columns),
            "primary_keys": list(t.spec.primary_keys),
            "pii_columns": [{
                "name": h.column, "category": h.category,
                "severity": h.severity, "confidence": h.confidence,
                "masked": h.masked,
            } for h in t.pii_hits],
            "warnings": list(t.warnings),
            "config_file": f"configs/{t.file_stem}.conf",
            "ddl_file": f"ddl/{t.file_stem}.sql" if t.ddl_text else None,
        })
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "mode": plan.source_mode,
            "database": plan.database,
            "path": plan.ddl_path,
        },
        "sink_type": plan.sink_type,
        "filters": {"include": plan.include, "exclude": plan.exclude},
        "pii": {
            "enabled": plan.pii,
            "strategy": plan.pii_strategy,
            "total_found": result.pii_columns,
            "total_masked": result.masked_columns,
        },
        "tables": tables,
        "skipped": [{"table": t, "reason": r} for t, r in result.skipped],
        "summary": {
            "tables": len(result.tables),
            "columns": sum(len(t.spec.columns) for t in result.tables),
            "pii_columns": result.pii_columns,
            "masked_columns": result.masked_columns,
            "warnings": (len(result.warnings)
                         + sum(len(t.warnings) for t in result.tables)),
            "unmapped_types": result.unmapped_count,
        },
        "warnings": list(result.warnings),
    }


def render_markdown(result: SyncResult, lang: str = "zh") -> str:
    t = SYNC_I18N[normalize_lang(lang)]
    plan = result.plan
    lines = [f"# {t['rpt_title']}", ""]
    if plan.source_mode == "live":
        lines.append(t["rpt_source_live"].format(database=plan.database or "?"))
    else:
        lines.append(t["rpt_source_ddl"].format(
            path=plan.ddl_path or "(inline)"))
    lines.append(t["rpt_sink"].format(sink=plan.sink_type))
    if plan.include or plan.exclude:
        lines.append(t["rpt_filters"].format(
            include=plan.include or "-", exclude=plan.exclude or "-"))
    lines += ["", t["rpt_summary"].format(
        tables=len(result.tables),
        columns=sum(len(x.spec.columns) for x in result.tables),
        pii=result.pii_columns, masked=result.masked_columns,
        warnings=(len(result.warnings)
                  + sum(len(x.warnings) for x in result.tables)),
        unmapped=result.unmapped_count), ""]

    if result.pii_columns and not plan.pii:
        lines += [f"**{t['rpt_pii_off_hint']}**", ""]

    if not result.tables:
        lines += [t["rpt_empty"], ""]
    else:
        lines += [f"## {t['rpt_tables']}", "", t["rpt_tables_cols"],
                  "|---|---|---|---|---|"]
        for x in result.tables:
            pii = ", ".join(
                f"{h.column}({h.category}{'' if h.masked else '?'})"
                for h in x.pii_hits) or t["rpt_none"]
            pk = ", ".join(x.spec.primary_keys) or t["rpt_none"]
            lines.append(
                f"| {x.spec.full_name} | {len(x.spec.columns)} | {pk} "
                f"| {pii} | {len(x.warnings)} |")
        lines.append("")

    if result.skipped:
        lines += [f"## {t['rpt_skipped']}", ""]
        lines += [f"- {name}: {reason}" for name, reason in result.skipped]
        lines.append("")

    all_warnings = list(result.warnings) + [
        w for x in result.tables for w in x.warnings]
    if all_warnings:
        lines += [f"## {t['rpt_warnings']}", ""]
        lines += [f"- {w}" for w in all_warnings]
        lines.append("")

    lines += [t["rpt_disclaimer"], ""]
    return "\n".join(lines)
