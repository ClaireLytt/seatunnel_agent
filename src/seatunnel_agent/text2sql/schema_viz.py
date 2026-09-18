"""ER diagram generation from SchemaStore + JoinAdvisor data.

Produces Mermaid ``erDiagram`` syntax and an embeddable HTML snippet
that renders it via the Mermaid.js library.
"""

from __future__ import annotations

import re

from .schema import SchemaStore
from .join_advisor import suggest_joins


def _sanitize_id(name: str) -> str:
    """Replace dots and special characters with underscores for Mermaid entity names."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _sanitize_dtype(dtype: str) -> str:
    """Sanitize column dtype for safe Mermaid rendering."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", dtype)


def generate_er_mermaid(
    store: SchemaStore,
    max_tables: int = 30,
    max_cols: int = 15,
) -> str:
    """Generate a Mermaid ``erDiagram`` string from a SchemaStore.

    Relationships are discovered by calling :func:`suggest_joins` for each
    table.  Duplicate relationships (A-B same as B-A) are deduplicated.

    Parameters
    ----------
    store:
        The schema store to visualize.
    max_tables:
        Cap on the number of tables rendered (to keep diagrams readable).
    max_cols:
        Maximum columns shown per entity block.
    """
    if len(store) == 0:
        return "erDiagram\n"

    tables = store.tables[:max_tables]

    # -- Collect relationships (deduplicated) --
    seen: set[tuple[str, str]] = set()
    relationships: list[str] = []

    for table in tables:
        joins = suggest_joins(table.full_name, store)
        for j in joins:
            pair = tuple(sorted([j.table_a, j.table_b]))
            if pair in seen:
                continue
            seen.add(pair)

            entity_a = _sanitize_id(j.table_a)
            entity_b = _sanitize_id(j.table_b)
            col_a = _sanitize_id(j.column_a)
            col_b = _sanitize_id(j.column_b)

            if j.match_type == "fk_pattern":
                connector = "}o--||"
            else:
                connector = "}o--o{"

            relationships.append(
                f'    {entity_a} {connector} {entity_b} : "{col_a} = {col_b}"'
            )

    # -- Build entity blocks --
    entity_blocks: list[str] = []
    for table in tables:
        safe_name = _sanitize_id(table.full_name)
        cols = table.columns[:max_cols]
        if not cols:
            entity_blocks.append(f"    {safe_name} {{}}")
            continue
        lines = [f"    {safe_name} {{"]
        for col in cols:
            safe_dtype = _sanitize_dtype(col.dtype) or "unknown"
            safe_col = _sanitize_id(col.name)
            lines.append(f"        {safe_dtype} {safe_col}")
        if len(table.columns) > max_cols:
            lines.append(f"        ___ ___more_{len(table.columns) - max_cols}___")
        lines.append("    }")
        entity_blocks.append("\n".join(lines))

    parts = ["erDiagram"]
    if relationships:
        parts.extend(relationships)
    parts.extend(entity_blocks)

    return "\n".join(parts) + "\n"


def generate_er_html(store: SchemaStore, lang: str = "en") -> str:
    """Return an HTML snippet that renders the ER diagram using Mermaid.js.

    The result is a self-contained ``<div>`` suitable for embedding in a
    Gradio ``gr.HTML`` component.
    """
    mermaid_code = generate_er_mermaid(store)

    title = "ER Diagram" if lang != "zh" else "ER 关系图"

    return f"""\
<div style="max-height:600px;overflow:auto;border:1px solid #e5e7eb;\
border-radius:8px;padding:16px;background:#fff;">
  <h3 style="margin:0 0 12px 0;font-size:15px;color:#333;">{title}</h3>
  <pre class="mermaid">
{mermaid_code}
  </pre>
</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
</script>
"""
