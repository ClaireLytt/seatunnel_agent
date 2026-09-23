"""Rendering: mermaid flowcharts, markdown trees and the final Chinese report."""

from __future__ import annotations

import html
import re

from .config import MAX_MERMAID_NODES
from .graph import (
    FIELD_LABELS,
    ChainResult,
    ColumnImpactResult,
    HealthReport,
    LineageGraph,
    SlaImpactResult,
    TableNode,
)
from .report import LineageReport

AGGREGATE_THRESHOLD = 150

LAYER_COLORS = {
    "ods": "#94a3b8",
    "dwd": "#60a5fa",
    "dwm": "#34d399",
    "dws": "#fbbf24",
    "ads": "#f87171",
    "dim": "#a78bfa",
    "": "#e5e7eb",
}

_ID_SANITIZE_RE = re.compile(r"[^0-9A-Za-z_]")


def mermaid_id(name: str) -> str:
    sanitized = _ID_SANITIZE_RE.sub("_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"t_{sanitized}"
    return sanitized or "unknown"


class _IdMap:
    """Collision-safe mermaid ids: sanitization can map distinct names
    (``a.b-c`` / ``a.b_c``) to the same id, silently merging nodes."""

    def __init__(self) -> None:
        self._ids: dict[str, str] = {}
        self._used: set[str] = set()

    def get(self, name: str) -> str:
        nid = self._ids.get(name)
        if nid is None:
            base = mermaid_id(name)
            nid, i = base, 2
            while nid in self._used:
                nid = f"{base}_{i}"
                i += 1
            self._used.add(nid)
            self._ids[name] = nid
        return nid


def _norm_layer(layer: str) -> str:
    layer = layer.strip().lower()
    return layer if layer in LAYER_COLORS else ""


def _node_label(node: TableNode, is_root: bool) -> str:
    parts = [node.name]
    meta_bits = []
    if node.layer:
        meta_bits.append(node.layer)
    if node.source_type:
        meta_bits.append(node.source_type)
    if meta_bits:
        parts.append(f"({' / '.join(meta_bits)})")
    if node.is_sla:
        suffix = f" {node.sla_time}" if node.sla_time else ""
        parts.append(f"⏰ SLA{suffix}")
    label = "<br/>".join(html.escape(p) for p in parts)
    if is_root:
        label = f"<b>{label}</b>"
    return label


def _select_nodes(chain: ChainResult, cap: int) -> tuple[set[str], bool]:
    """Keep nodes closest to the root when over the mermaid cap."""
    if len(chain.nodes) <= cap:
        return set(chain.nodes), False
    ordered = sorted(
        chain.nodes,
        key=lambda n: (abs(chain.depth_of.get(n, 0)), n),
    )
    return set(ordered[:cap]), True


def _group_key(node: TableNode) -> str:
    return node.database or node.layer or "other"


def _render_aggregated(chain: ChainResult) -> str:
    """Grouped view for huge chains: one node per database/layer group."""
    groups: dict[str, int] = {}
    group_of: dict[str, str] = {}
    for name, node in chain.nodes.items():
        key = _group_key(node)
        groups[key] = groups.get(key, 0) + 1
        group_of[name] = key
    edge_counts: dict[tuple[str, str], int] = {}
    for src, dst in chain.edges:
        gs, gd = group_of.get(src), group_of.get(dst)
        if gs is None or gd is None or gs == gd:
            continue
        edge_counts[(gs, gd)] = edge_counts.get((gs, gd), 0) + 1

    lines = ["flowchart LR"]
    ids = _IdMap()
    root_group = group_of.get(chain.root)
    for key in sorted(groups):
        label = f"{html.escape(key)}（{groups[key]} 张表）"
        if key == root_group:
            label = f"<b>{label}</b><br/>根表: {html.escape(chain.root)}"
        lines.append(f'    {ids.get(key)}["{label}"]')
    for (gs, gd), count in sorted(edge_counts.items()):
        lines.append(f"    {ids.get(gs)} -->|{count}| {ids.get(gd)}")
    if root_group is not None:
        lines.append("    classDef root_mark stroke:#111827,stroke-width:3px")
        lines.append(f"    class {ids.get(root_group)} root_mark")
    lines.append(
        f"    %% 节点过多已聚合为分层视图"
        f"（原始 {len(chain.nodes)} 表 / {len(chain.edges)} 边）"
    )
    return "\n".join(lines)


def render_mermaid(
    chain: ChainResult,
    max_nodes: int = MAX_MERMAID_NODES,
    aggregate_threshold: int = AGGREGATE_THRESHOLD,
) -> str:
    if chain.missing_root or not chain.nodes:
        return f'flowchart LR\n    empty["未找到表 {html.escape(chain.root)}"]'

    if len(chain.nodes) > aggregate_threshold:
        return _render_aggregated(chain)

    kept, pruned = _select_nodes(chain, max_nodes)
    lines = ["flowchart LR"]
    used_layers: set[str] = set()
    sla_ids: list[str] = []
    ids = _IdMap()
    root_id = ids.get(chain.root)

    for name in sorted(kept, key=lambda n: (chain.depth_of.get(n, 0), n)):
        node = chain.nodes[name]
        nid = ids.get(name)
        lines.append(f'    {nid}["{_node_label(node, name == chain.root)}"]')
        layer = _norm_layer(node.layer)
        used_layers.add(layer)
        lines.append(f"    class {nid} layer_{layer or 'none'}")
        if node.is_sla:
            sla_ids.append(nid)

    dashed = False
    for src, dst in chain.edges:
        if src in kept and dst in kept:
            meta = chain.edge_meta.get((src, dst))
            if meta is not None and meta.confidence != "high":
                lines.append(f"    {ids.get(src)} -.-> {ids.get(dst)}")
                dashed = True
            else:
                lines.append(f"    {ids.get(src)} --> {ids.get(dst)}")
    if dashed:
        lines.append("    %% 虚线 = 启发式/低置信度血缘边")

    for layer in sorted(used_layers):
        color = LAYER_COLORS.get(layer, LAYER_COLORS[""])
        lines.append(
            f"    classDef layer_{layer or 'none'} "
            f"fill:{color},stroke:#334155,color:#111827"
        )
    if sla_ids:
        lines.append("    classDef sla_mark stroke:#dc2626,stroke-width:3px")
        lines.append(f"    class {','.join(sla_ids)} sla_mark")
    if chain.root in kept:
        lines.append("    classDef root_mark stroke:#111827,stroke-width:3px")
        lines.append(f"    class {root_id} root_mark")

    if pruned or chain.truncated:
        hidden = len(chain.nodes) - len(kept)
        note = "链路过大已截断"
        if hidden > 0:
            note += f"，另有 {hidden} 个节点未展示"
        lines.append(f"    %% {note}")
    return "\n".join(lines)


def render_column_mermaid(impact: ColumnImpactResult) -> str:
    root = f"{impact.root_table}.{impact.root_column}"
    if impact.missing_root:
        return f'flowchart LR\n    empty["未找到表 {html.escape(impact.root_table)}"]'
    if impact.degraded and impact.table_fallback:
        return render_mermaid(impact.table_fallback)
    if not impact.edges:
        return f'flowchart LR\n    {mermaid_id(root)}["{html.escape(root)}<br/>无下游字段血缘"]'

    lines = ["flowchart LR"]
    ids = _IdMap()
    declared: set[str] = set()

    def declare(table: str, column: str, is_root: bool = False) -> str:
        full = f"{table}.{column}"
        nid = ids.get(full)
        if full not in declared:
            declared.add(full)
            label = html.escape(full)
            if is_root:
                label = f"<b>{label}</b>"
            lines.append(f'    {nid}["{label}"]')
        return nid

    declare(impact.root_table, impact.root_column, is_root=True)
    for edge in impact.edges:
        src = declare(edge.src_table, edge.src_column)
        dst = declare(edge.dst_table, edge.dst_column)
        if edge.is_aggregation:
            lines.append(f"    {src} -->|聚合| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")
    if impact.truncated:
        lines.append("    %% 链路过大已截断")
    return "\n".join(lines)


def select_mermaid(
    chain: ChainResult | None,
    impact: ColumnImpactResult | None,
    max_nodes: int = MAX_MERMAID_NODES,
    prefer_impact: bool = True,
) -> str:
    """Column-level graph when a usable impact result exists (and is preferred),
    else the table-level chain graph, else empty."""
    if prefer_impact and impact is not None and not impact.degraded and impact.edges:
        return render_column_mermaid(impact)
    if chain is not None and not chain.missing_root:
        return render_mermaid(chain, max_nodes)
    return ""


def render_tree(chain: ChainResult) -> str:
    """Markdown indented tree fallback (upstream above root, downstream below)."""
    if chain.missing_root:
        return f"未找到表 `{chain.root}`。"
    lines: list[str] = []
    # Nearest upstream first, deeper ancestors nested below it — starting at
    # indent 0 so CommonMark never mistakes the first item for a code block.
    ups = sorted(
        (n for n, d in chain.depth_of.items() if d < 0),
        key=lambda n: (-chain.depth_of[n], n),
    )
    downs = sorted(
        (n for n, d in chain.depth_of.items() if d > 0),
        key=lambda n: (chain.depth_of[n], n),
    )
    for name in ups:
        depth = abs(chain.depth_of[name])
        node = chain.nodes.get(name)
        layer = f" ({node.layer})" if node and node.layer else ""
        lines.append(f"{'  ' * (depth - 1)}- ⬆ `{name}`{layer}")
    lines.append(f"- **`{chain.root}`**（当前表）")
    for name in downs:
        depth = chain.depth_of[name]
        node = chain.nodes.get(name)
        layer = f" ({node.layer})" if node and node.layer else ""
        sla = " ⏰SLA" if node and node.is_sla else ""
        lines.append(f"{'  ' * depth}- ⬇ `{name}`{layer}{sla}")
    if chain.truncated:
        lines.append("- …（链路过大已截断，可增大深度或收窄方向）")
    return "\n".join(lines)


def render_path(path: list[str] | None, src: str, dst: str,
                graph: LineageGraph | None = None) -> str:
    """Markdown for a src→dst path query (None = no path found)."""
    if not path:
        return f"`{src}` 与 `{dst}` 之间没有找到血缘路径（双向均已尝试）。"
    parts = []
    for name in path:
        node = graph.get(name) if graph else None
        layer = f"({node.layer})" if node and node.layer else ""
        parts.append(f"`{name}`{layer}")
    lines = [
        f"`{path[0]}` → `{path[-1]}` 共 **{len(path) - 1}** 跳：",
        "",
        " → ".join(parts),
    ]
    return "\n".join(lines)


def render_path_mermaid(path: list[str] | None,
                        graph: LineageGraph | None = None) -> str:
    if not path:
        return 'flowchart LR\n    empty["未找到路径"]'
    lines = ["flowchart LR"]
    ids = _IdMap()
    for i, name in enumerate(path):
        node = graph.get(name) if graph else None
        label = _node_label(node, i in (0, len(path) - 1)) if node \
            else html.escape(name)
        lines.append(f'    {ids.get(name)}["{label}"]')
    for a, b in zip(path, path[1:]):
        lines.append(f"    {ids.get(a)} --> {ids.get(b)}")
    return "\n".join(lines)


def render_sla_impact(impact: SlaImpactResult) -> str:
    """Chinese report section: downstream SLA/baseline tasks at risk."""
    if impact.missing_root:
        return f"未找到表 `{impact.root}`。"
    title = f"## SLA 延迟影响分析：`{impact.root}`"
    if impact.delay_hours > 0:
        title += f"（假设延迟 {impact.delay_hours:g} 小时）"
    lines = [title, ""]
    if not impact.affected:
        lines.append("下游链路上没有 SLA 或基线任务，延迟不会直接影响承诺产出。")
        return "\n".join(lines)
    lines.extend([
        f"下游共 **{len(impact.affected)}** 个 SLA/基线任务受影响"
        "（按距离与产出时间排序）：",
        "",
        f"| 距离(跳) | {FIELD_LABELS['table']} | {FIELD_LABELS['layer']} | "
        f"{FIELD_LABELS['is_sla']} | {FIELD_LABELS['sla_time']} | "
        f"{FIELD_LABELS['baselines']} |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for node, hops in impact.affected:
        lines.append(
            f"| {hops} | `{node.name}` | {node.layer or '-'} | "
            f"{'是' if node.is_sla else '否'} | {node.sla_time or '-'} | "
            f"{'、'.join(node.baselines) or '-'} |"
        )
    if impact.delay_hours > 0:
        lines.extend([
            "",
            f"延迟 {impact.delay_hours:g} 小时将沿上表链路传导；"
            "距离越近、SLA 产出时间越早的任务破线风险越高，请优先关注。",
        ])
    if impact.truncated:
        lines.append("- …（链路过大已截断）")
    return "\n".join(lines)


_CONF_LABELS = {"high": "高", "medium": "中", "low": "低"}


def _confidence_line(stats: dict) -> list[str]:
    sources = stats.get("edge_sources") or {}
    conf = stats.get("edge_confidence") or {}
    if not sources and not conf:
        return []
    bits = []
    if sources:
        bits.append(
            "来源 " + " / ".join(f"{k}:{v}" for k, v in sorted(sources.items()))
        )
    if conf:
        bits.append(
            "置信度 " + " / ".join(
                f"{_CONF_LABELS.get(k, k)}:{v}" for k, v in sorted(conf.items())
            )
        )
    return [f"- 边 {' · '.join(bits)}"]


def render_health(report: HealthReport, sample: int = 30) -> str:
    """Chinese governance health-check report."""
    stats = report.stats
    lines = [
        "## 血缘治理体检报告",
        "",
        f"- 表 **{stats.get('tables', 0)}** 张 · 血缘边 **{stats.get('edges', 0)}** 条 · "
        f"字段级血缘 **{stats.get('column_edges', 0)}** 条 · "
        f"SLA 表 **{stats.get('sla_tables', 0)}** 张",
        *_confidence_line(stats),
        "",
        f"### 环依赖（{len(report.cycles)} 个）",
        "",
    ]
    if report.cycles:
        lines.append("以下环路会导致调度依赖死锁或口径混乱，需要拆解：")
        lines.extend(
            f"- {' → '.join(f'`{n}`' for n in cycle)}" for cycle in report.cycles
        )
    else:
        lines.append("未检测到环依赖。")
    lines.extend(["", f"### 孤立表（{len(report.isolated)} 张，无上下游）", ""])
    if report.isolated:
        lines.append("既没有上游也没有下游，可能是未接入血缘或已废弃：")
        lines.extend(f"- `{n}`" for n in report.isolated[:sample])
        if len(report.isolated) > sample:
            lines.append(f"- …另有 {len(report.isolated) - sample} 张未展示")
    else:
        lines.append("没有孤立表。")
    lines.extend([
        "",
        f"### 无下游表（{len(report.no_downstream)} 张，可评估下线）",
        "",
    ])
    if report.no_downstream:
        lines.append("有上游加工但没有任何消费方，建议确认后下线以节省成本：")
        lines.extend(f"- `{n}`" for n in report.no_downstream[:sample])
        if len(report.no_downstream) > sample:
            lines.append(f"- …另有 {len(report.no_downstream) - sample} 张未展示")
    else:
        lines.append("没有可下线候选表。")
    return "\n".join(lines)


def _render_sla_section(report: LineageReport) -> str:
    if not report.sla_nodes and not report.baseline_nodes:
        return "链路上没有 SLA 或基线任务。"
    header = (
        f"| {FIELD_LABELS['table']} | {FIELD_LABELS['layer']} | "
        f"{FIELD_LABELS['is_sla']} | {FIELD_LABELS['sla_time']} | "
        f"{FIELD_LABELS['baselines']} |"
    )
    lines = [header, "| --- | --- | --- | --- | --- |"]
    seen: set[str] = set()
    for node in report.sla_nodes + report.baseline_nodes:
        if node.name in seen:
            continue
        seen.add(node.name)
        lines.append(
            f"| `{node.name}` | {node.layer or '-'} | "
            f"{'是' if node.is_sla else '否'} | {node.sla_time or '-'} | "
            f"{'、'.join(node.baselines) or '-'} |"
        )
    return "\n".join(lines)


def _render_impact_section(impact: ColumnImpactResult) -> str:
    root = f"{impact.root_table}.{impact.root_column}"
    if impact.missing_root:
        return f"未找到表 `{impact.root_table}`。"
    if impact.degraded:
        count = len(impact.table_fallback.nodes) - 1 if impact.table_fallback else 0
        return (
            f"字段 `{root}` 没有可用的字段级血缘（SQL 未覆盖或解析受限），"
            f"已降级为**表级**下游分析：影响约 {max(count, 0)} 张下游表。"
        )
    if not impact.impacted:
        return f"字段 `{root}` 没有已知的下游字段依赖。"
    lines = [f"字段 `{root}` 影响以下 {len(impact.impacted)} 个下游字段：", ""]
    lines.extend(f"- `{item}`" for item in impact.impacted)
    if impact.truncated:
        lines.append("- …（链路过大已截断）")
    return "\n".join(lines)


def render_report(report: LineageReport) -> str:
    stats = report.stats()
    lines = [f"## 血缘分析报告：`{report.root_table}`", ""]
    if report.chain and report.chain.missing_root:
        lines.append(f"未在血缘图中找到表 `{report.root_table}`。")
        return "\n".join(lines)

    if report.mermaid:
        lines.extend(["### 血缘图", "", "```mermaid", report.mermaid, "```", ""])
    if report.chain:
        lines.extend([
            "### 链路概览",
            "",
            f"- 上游 **{stats['upstream']}** 张 · 下游 **{stats['downstream']}** 张"
            f"（边 {stats['edges']} 条，方向：{report.direction}）",
            "",
            render_tree(report.chain),
            "",
        ])
    lines.extend(["### SLA 与基线", "", _render_sla_section(report), ""])
    if report.column_impact:
        lines.extend([
            "### 字段影响分析",
            "",
            _render_impact_section(report.column_impact),
            "",
        ])
    if report.summary:
        lines.extend(["### 总体结论", "", report.summary, ""])
    return "\n".join(lines).rstrip() + "\n"


_MERMAID_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { margin: 0; padding: 8px; background: #ffffff; font-family: sans-serif; }
  .mermaid { text-align: center; }
</style>
</head>
<body>
<pre class="mermaid">
__MERMAID_SOURCE__
</pre>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
mermaid.run({ querySelector: ".mermaid" }).then(function () {
  // srcdoc iframes share the parent origin: a node click fills the hidden
  // jump textbox on the lineage page and triggers a re-query on that table.
  document.querySelectorAll(".node").forEach(function (n) {
    n.style.cursor = "pointer";
    n.addEventListener("click", function () {
      var m = (n.textContent || "").trim().match(/^[A-Za-z0-9_.$-]+/);
      if (!m) return;
      try {
        var pwin = window.parent;
        var inp = pwin.document.querySelector(
          "#st-lin-node-jump textarea, #st-lin-node-jump input");
        if (!inp) return;
        var proto = inp.tagName === "TEXTAREA"
          ? pwin.HTMLTextAreaElement.prototype
          : pwin.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, "value").set.call(inp, m[0]);
        inp.dispatchEvent(new Event("input", { bubbles: true }));
        setTimeout(function () {
          var btn = pwin.document.querySelector("#st-lin-node-jump-btn");
          if (btn) btn.click();
        }, 80);
      } catch (e) { /* cross-origin embed: jump silently unavailable */ }
    });
  });
}).catch(function () {});
</script>
</body>
</html>"""


def mermaid_html(mermaid_src: str) -> str:
    """Standalone HTML document, meant for <iframe srcdoc> embedding in Gradio."""
    return _MERMAID_HTML_TEMPLATE.replace("__MERMAID_SOURCE__", html.escape(mermaid_src))
