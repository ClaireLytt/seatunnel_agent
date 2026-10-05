"""Unified NL catalog search (数据目录: NL 找表/找指标/找取值).

One question — "有没有存用户收货地址的表" — answered across three asset
kinds in a single ranked result, all deterministic and LLM-free:

- tables  : HybridRetriever fused ranking (keyword × BM25 × vector)
- metrics : the semantic layer's alias/description matching (fused too)
- values  : ValueIndex cell-value hits ("华东" lives in dim_region.region)

Pure delegation — this module owns no scoring of its own, so catalog
results always agree with what the Chat BI agent itself would retrieve.
"""

from __future__ import annotations

from typing import Any

from .metrics import MetricStore
from .retrieval import HybridRetriever
from .schema import SchemaStore


def search_catalog(
    query: str,
    store: SchemaStore,
    metric_store: MetricStore | None = None,
    value_index: Any = None,
    retriever: HybridRetriever | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Rank tables, metrics and sampled values for one NL query."""
    query = (query or "").strip()
    if not query:
        return {"query": "", "tables": [], "metrics": [], "value_hits": []}
    if retriever is None:
        retriever = HybridRetriever(store, metric_store=metric_store)

    tables = [
        {
            "table": m.table.full_name,
            "comment": m.table.comment,
            "score": m.score,
            "column_hits": list(m.column_hits),
        }
        for m in retriever.rank(query, top_n=top_n)
    ]
    metrics = [
        {
            "metric": m.metric.name,
            "display_name": m.metric.display_name,
            "description": m.metric.description,
            "table": m.metric.table,
            "score": round(float(m.score), 6),
            "hits": list(m.hits),
        }
        for m in retriever.rank_metrics(query, top_n=top_n)
    ]
    value_hits = []
    if value_index is not None:
        value_hits = [
            {"value": h.value, "table": h.table, "column": h.column}
            for h in value_index.search(query)
        ]
    return {
        "query": query,
        "tables": tables,
        "metrics": metrics,
        "value_hits": value_hits,
    }


def render_catalog_markdown(result: dict[str, Any]) -> str:
    """Terminal/report-friendly Markdown of a search_catalog result."""
    lines = [f"# 数据目录检索: {result.get('query', '')}", ""]

    metrics = result.get("metrics") or []
    if metrics:
        lines += ["## 指标", "", "| 指标 | 名称 | 口径表 | 匹配 |", "|---|---|---|---|"]
        lines += [
            f"| {m['metric']} | {m['display_name']} | {m['table']} "
            f"| {', '.join(m['hits']) or '-'} |"
            for m in metrics
        ]
        lines.append("")

    tables = result.get("tables") or []
    if tables:
        lines += ["## 表", "", "| 表 | 注释 | 命中列 |", "|---|---|---|"]
        lines += [
            f"| {t['table']} | {t['comment'] or '-'} "
            f"| {', '.join(t['column_hits']) or '-'} |"
            for t in tables
        ]
        lines.append("")

    hits = result.get("value_hits") or []
    if hits:
        lines += ["## 取值命中", "", "| 取值 | 表 | 列 |", "|---|---|---|"]
        lines += [f"| {h['value']} | {h['table']} | {h['column']} |" for h in hits]
        lines.append("")

    if not (metrics or tables or hits):
        lines.append("没有匹配的资产。")
    return "\n".join(lines)
