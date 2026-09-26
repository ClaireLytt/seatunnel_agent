# -*- coding: utf-8 -*-
"""Data dictionary generation from the lineage graph.

The graph already knows every table, its layer, its column-level in/out
edges and where each column comes from — this module renders that as a
Markdown data dictionary. Deterministic by default; an optional LLM pass
adds one-line table descriptions (clearly marked, additive only).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from .graph import LineageGraph

if TYPE_CHECKING:  # pragma: no cover
    from ..config import Settings

_LAYER_ORDER = {"ods": 0, "dwd": 1, "dwm": 2, "dws": 3, "ads": 4, "rpt": 5}


def _layer_of(name: str, node_layer: str) -> str:
    if node_layer:
        return node_layer
    db = name.split(".", 1)[0].lower()
    for prefix in _LAYER_ORDER:
        if db.startswith(prefix):
            return prefix
    return ""


def _sort_key(name: str, layer: str) -> tuple[int, str]:
    return (_LAYER_ORDER.get(layer, 9), name)


def build_dictionary(graph: LineageGraph) -> list[dict[str, Any]]:
    """One entry per table: layer, upstream/downstream tables, and every
    column seen in lineage with its sources and expression."""
    columns: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (dst_table, dst_col), edges in graph.column_up.items():
        info = columns[dst_table].setdefault(
            dst_col, {"sources": [], "expression": "",
                      "is_aggregation": False})
        for e in edges:
            src = f"{e.src_table}.{e.src_column}"
            if src not in info["sources"]:
                info["sources"].append(src)
            if e.expression:
                info["expression"] = e.expression
            info["is_aggregation"] = info["is_aggregation"] or e.is_aggregation
    # source-only columns (read but never written in the scanned SQL)
    for (src_table, src_col) in graph.column_down:
        columns[src_table].setdefault(
            src_col, {"sources": [], "expression": "",
                      "is_aggregation": False})

    entries: list[dict[str, Any]] = []
    for name, node in graph.nodes.items():
        layer = _layer_of(name, node.layer)
        entries.append({
            "table": name,
            "layer": layer,
            "is_sla": node.is_sla,
            "upstreams": sorted(graph.upstream.get(name, ())),
            "downstreams": sorted(graph.downstream.get(name, ())),
            "columns": {
                col: columns[name][col]
                for col in sorted(columns.get(name, {}))
            },
            "description": "",
        })
    entries.sort(key=lambda e: _sort_key(e["table"], e["layer"]))
    return entries


def render_dictionary_markdown(
    entries: list[dict[str, Any]], lang: str = "zh",
) -> str:
    zh = not (lang or "").lower().startswith("en")
    title = "# 数据字典" if zh else "# Data Dictionary"
    lines = [title, ""]
    lines.append(("共 {n} 表 · 按分层排序 · 由血缘图生成，未连接数据库"
                  if zh else
                  "{n} tables · ordered by layer · generated from the "
                  "lineage graph, no database connection").format(
                      n=len(entries)))
    lines.append("")
    for e in entries:
        badge = " 🕐SLA" if e["is_sla"] else ""
        layer = f" `{e['layer']}`" if e["layer"] else ""
        lines.append(f"## {e['table']}{layer}{badge}")
        if e["description"]:
            lines.append(f"> {e['description']}  <sub>llm-generated</sub>")
        up = ", ".join(f"`{t}`" for t in e["upstreams"]) or "-"
        down = ", ".join(f"`{t}`" for t in e["downstreams"]) or "-"
        lines.append(("**上游**: {u}  \n**下游**: {d}" if zh else
                      "**Upstream**: {u}  \n**Downstream**: {d}"
                      ).format(u=up, d=down))
        cols = e["columns"]
        if cols:
            lines.append("")
            lines.append("| " + ("字段 | 来源 | 表达式" if zh
                                 else "column | sources | expression") + " |")
            lines.append("|---|---|---|")
            for col, info in cols.items():
                srcs = ", ".join(f"`{s}`" for s in info["sources"]) or "-"
                expr = info["expression"]
                if info["is_aggregation"] and expr:
                    expr += " ⚡"
                lines.append(f"| `{col}` | {srcs} | "
                             f"{('`' + expr + '`') if expr else '-'} |")
        lines.append("")
    return "\n".join(lines)


_DESCRIBE_PROMPT = """\
You are a data-warehouse documentation writer. For every table below,
write ONE short sentence in {language} describing what the table holds,
judging only from its name, layer, columns and lineage. Output strictly
one line per table in the form `table_name: description` — no markdown,
no extra lines, no guesses about business facts you cannot infer.
"""


def add_llm_descriptions(
    settings: "Settings", entries: list[dict[str, Any]], lang: str = "zh",
) -> int:
    """Optional LLM pass: fill ``description`` per table (marked
    llm-generated by the renderer). Returns how many were filled; the
    deterministic entries are never otherwise modified."""
    from ..llm import LLMClient

    zh = not (lang or "").lower().startswith("en")
    summary = "\n".join(
        f"- {e['table']} (layer={e['layer'] or '?'}; "
        f"columns={', '.join(list(e['columns'])[:12]) or '?'}; "
        f"upstream={', '.join(e['upstreams'][:5]) or '-'})"
        for e in entries
    )
    llm = LLMClient(settings)
    resp = llm.chat(
        _DESCRIBE_PROMPT.format(language="Chinese" if zh else "English"),
        [{"role": "user", "content": summary}],
    )
    by_table = {e["table"]: e for e in entries}
    filled = 0
    for line in (resp.reply_text or "").splitlines():
        if ":" not in line and "：" not in line:
            continue
        sep = ":" if ":" in line else "："
        name, _, desc = line.partition(sep)
        entry = by_table.get(name.strip().strip("`-* "))
        if entry is not None and desc.strip():
            entry["description"] = desc.strip()
            filled += 1
    return filled
