"""Root-cause orchestration (异动根因联动): attribution × lineage × logs.

Attribution answers *where* a metric moved (which dimension values);
this module chains the next hop toward *why*:

1. attribution  — reuse ``run_attribution`` (ratio metrics are decomposed
   into numerator/denominator, same as the agent tool)
2. lineage      — the metric's source tables' upstream chain
   (``data_lineage.build_graph`` over the warehouse SQL directory)
3. logs         — ``log_inspect`` error clusters, correlated with the
   involved tables by name

Everything here is deterministic orchestration and correlation; the LLM
(when any) only narrates the resulting facts. Boundaries: schema-drift
correlation needs two DDL snapshots and is NOT attempted here; log
correlation is name-based (a cluster that never mentions a table name
will not be linked to it).
"""

from __future__ import annotations

from typing import Any, Callable

from .attribution import (
    AttributionResult,
    attribution_to_dict,
    ratio_factor_split,
    run_attribution,
)
from .metrics import MetricDef, MetricStore, ratio_sides
from .partition import TimeRange
from .schema import SchemaStore

ExecuteFn = Callable[[str], tuple[list[str], list[tuple]]]

#: max upstream tables carried into the report / correlation
_MAX_UPSTREAM = 30
#: max log clusters carried into the report
_MAX_CLUSTERS = 10


def _bare_name(table: str) -> str:
    return table.rsplit(".", 1)[-1].lower()


def _upstream_tables(graph: Any, roots: list[str], depth: int) -> list[str]:
    seen: list[str] = []
    for root in roots:
        chain = graph.upstream_of(root, depth=depth)
        for t, d in sorted(chain.depth_of.items()):
            if t != root and d < 0 and t not in seen:
                seen.append(t)
    return seen[:_MAX_UPSTREAM]


def _correlate_logs(
    clusters: list[Any], tables: list[str],
) -> list[dict[str, Any]]:
    """Error clusters whose text mentions any involved table (name-based)."""
    suspects: list[dict[str, Any]] = []
    names = {t: _bare_name(t) for t in tables}
    for cluster in clusters:
        haystack = " ".join([
            cluster.template or "", cluster.sample or "",
            cluster.top_frame or "", " ".join(cluster.files),
        ]).lower()
        hit = [t for t, bare in names.items()
               if t.lower() in haystack or bare in haystack]
        if hit:
            suspects.append({
                "tables": hit,
                "level": cluster.level,
                "exception": cluster.exception,
                "template": cluster.template,
                "count": cluster.count,
                "last_ts": cluster.last_ts,
            })
    return suspects


def run_root_cause(
    metric: MetricDef,
    metric_store: MetricStore,
    schema_store: SchemaStore,
    execute_fn: ExecuteFn,
    curr_range: TimeRange,
    prev_range: TimeRange,
    lineage_sql_dir: str = "",
    log_dir: str = "",
    depth: int = 3,
) -> dict[str, Any]:
    """One-call root-cause report for '指标为什么异动'. Lineage and log
    hops are optional (empty dir = skipped, stated in the report)."""
    out: dict[str, Any] = {"metric": metric.name,
                           "display_name": metric.display_name}

    # 1) attribution (facts of the move)
    if metric.is_ratio:
        num, den = ratio_sides(metric, metric_store)
        num_res = run_attribution(
            num, metric_store, schema_store, execute_fn, curr_range, prev_range)
        den_res = run_attribution(
            den, metric_store, schema_store, execute_fn, curr_range, prev_range)
        out["attribution"] = {
            "type": "ratio",
            "numerator": attribution_to_dict(num_res),
            "denominator": attribution_to_dict(den_res),
        }
        split = ratio_factor_split(
            num_res.prev_total, num_res.curr_total,
            den_res.prev_total, den_res.curr_total)
        if split is not None:
            out["attribution"]["factor_split"] = split
        results: list[AttributionResult] = [num_res, den_res]
        source_tables = [num.table, den.table]
    else:
        res = run_attribution(
            metric, metric_store, schema_store, execute_fn,
            curr_range, prev_range)
        out["attribution"] = {"type": "additive", **attribution_to_dict(res)}
        results = [res]
        source_tables = [metric.table]
    out["source_tables"] = source_tables

    # 2) upstream chain (optional)
    upstream: list[str] = []
    if lineage_sql_dir:
        from ..data_lineage.loaders import build_graph

        graph, warnings = build_graph(sql_dir=lineage_sql_dir)
        upstream = _upstream_tables(graph, source_tables, depth)
        out["upstream"] = upstream
        if warnings:
            out["lineage_warnings"] = warnings[:5]
    else:
        out["upstream_skipped"] = "未提供数仓 SQL 目录，跳过上游血缘"

    # 3) log correlation (optional)
    suspects: list[dict[str, Any]] = []
    if log_dir:
        from ..log_inspect.clusterer import scan_dir

        report = scan_dir(log_dir)
        clusters = report.clusters[:_MAX_CLUSTERS]
        out["log_clusters"] = [c.to_dict() for c in clusters]
        suspects = _correlate_logs(clusters, source_tables + upstream)
        out["suspects"] = suspects
        if report.warnings:
            out["log_warnings"] = report.warnings[:5]
    else:
        out["logs_skipped"] = "未提供任务日志目录，跳过日志关联"

    # 4) deterministic conclusions — facts only, ready for narration
    conclusions: list[str] = []
    for res in results:
        rate = (f"{res.change_rate * 100:+.2f}%"
                if res.change_rate is not None else "N/A(基期为0)")
        line = (f"{res.display_name}: {res.prev_total:,.2f} -> "
                f"{res.curr_total:,.2f} ({rate})")
        if res.best_dimension:
            line += f"，最具解释力维度: {res.best_dimension}"
        conclusions.append(line)
    for s in suspects:
        conclusions.append(
            f"疑似根因: 表 {', '.join(s['tables'])} 关联 {s['level'].upper()} "
            f"日志 {s['count']} 次（{s['exception'] or s['template'][:60]}，"
            f"最近 {s['last_ts'] or '未知时间'}）"
        )
    if log_dir and not suspects:
        conclusions.append("日志中未发现与口径表/上游表直接关联的错误簇")
    out["conclusions"] = conclusions
    return out


def render_root_cause_markdown(report: dict[str, Any]) -> str:
    """Human-readable Markdown of a run_root_cause report."""
    lines = [f"# 根因分析: {report.get('display_name', report.get('metric'))}", ""]

    lines += ["## 结论", ""]
    lines += [f"- {c}" for c in report.get("conclusions", [])]
    lines.append("")

    attr = report.get("attribution") or {}
    if attr.get("type") == "ratio":
        for side in ("numerator", "denominator"):
            a = attr.get(side) or {}
            lines.append(
                f"- {side}: {a.get('display_name')} "
                f"{a.get('prev_total')} -> {a.get('curr_total')} "
                f"({a.get('change_rate_pct')}%)")
        lines.append("")

    upstream = report.get("upstream")
    if upstream is not None:
        lines += ["## 上游血缘", ""]
        lines.append("、".join(upstream) if upstream else "（血缘图中无上游）")
        lines.append("")
    elif report.get("upstream_skipped"):
        lines.append(f"> {report['upstream_skipped']}")

    suspects = report.get("suspects")
    if suspects:
        lines += ["## 疑似根因（日志关联）", "",
                  "| 表 | 级别 | 异常 | 次数 | 最近出现 |", "|---|---|---|---|---|"]
        lines += [
            f"| {', '.join(s['tables'])} | {s['level']} "
            f"| {s['exception'] or s['template'][:40]} | {s['count']} "
            f"| {s['last_ts'] or '-'} |"
            for s in suspects
        ]
        lines.append("")
    elif report.get("logs_skipped"):
        lines.append(f"> {report['logs_skipped']}")
    lines.append("")
    return "\n".join(lines)
