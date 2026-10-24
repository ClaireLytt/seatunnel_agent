"""Rendering: mermaid flowcharts, markdown trees and the final report.

Every public render function takes ``lang`` ("zh" default, "en") and pulls
its copy from the module i18n table; table/column/baseline NAMES are user
data and pass through untouched.
"""

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

# EN counterparts of graph.FIELD_LABELS (those stay zh: they double as
# TableNode.to_dict keys, a data contract we must not fork by language).
_FIELD_LABELS_EN = {
    "source_type": "type",
    "database": "database",
    "table": "table",
    "layer": "layer",
    "is_sla": "SLA?",
    "sla_time": "SLA time",
    "baselines": "baselines",
}

_I18N: dict[str, dict[str, str]] = {
    "zh": {
        # mermaid / tree / path
        "missing_table": "未找到表 {name}",
        "missing_table_md": "未找到表 `{name}`。",
        "agg_group": "{name}（{n} 张表）",
        "agg_root": "根表: {name}",
        "agg_note": "    %% 节点过多已聚合为分层视图（原始 {nodes} 表 / {edges} 边）",
        "dashed_note": "    %% 虚线 = 启发式/低置信度血缘边",
        "mermaid_truncated": "链路过大已截断",
        "mermaid_truncated_more": "，另有 {n} 个节点未展示",
        "no_col_lineage": "无下游字段血缘",
        "agg_edge": "聚合",
        "tree_root_suffix": "（当前表）",
        "tree_truncated": "- …（链路过大已截断，可增大深度或收窄方向）",
        "path_none": "`{src}` 与 `{dst}` 之间没有找到血缘路径（双向均已尝试）。",
        "path_head": "`{src}` → `{dst}` 共 **{n}** 跳：",
        "path_mermaid_none": "未找到路径",
        # SLA impact
        "sla_title": "## SLA 延迟影响分析：`{root}`",
        "sla_delay_suffix": "（假设延迟 {hours} 小时）",
        "sla_no_tasks": "下游链路上没有 SLA 或基线任务，延迟不会直接影响承诺产出。",
        "sla_count": "下游共 **{n}** 个 SLA/基线任务受影响（按距离与产出时间排序）：",
        "sla_hops": "距离(跳)",
        "sla_propagate": ("延迟 {hours} 小时将沿上表链路传导；"
                          "距离越近、SLA 产出时间越早的任务破线风险越高，请优先关注。"),
        "truncated_item": "- …（链路过大已截断）",
        "yes": "是",
        "no": "否",
        "list_sep": "、",
        # report sections
        "sla_section_none": "链路上没有 SLA 或基线任务。",
        "impact_degraded": ("字段 `{root}` 没有可用的字段级血缘（SQL 未覆盖或解析受限），"
                            "已降级为**表级**下游分析：影响约 {n} 张下游表。"),
        "impact_none": "字段 `{root}` 没有已知的下游字段依赖。",
        "impact_head": "字段 `{root}` 影响以下 {n} 个下游字段：",
        "report_title": "## 血缘分析报告：`{root}`",
        "report_missing": "未在血缘图中找到表 `{root}`。",
        "sec_graph": "### 血缘图",
        "sec_chain": "### 链路概览",
        "chain_stats": ("- 上游 **{up}** 张 · 下游 **{down}** 张"
                        "（边 {edges} 条，方向：{direction}）"),
        "sec_sla": "### SLA 与基线",
        "sec_impact": "### 字段影响分析",
        "sec_summary": "### 总体结论",
        # health report
        "h_title": "## 血缘治理体检报告",
        "h_stats": ("- 表 **{tables}** 张 · 血缘边 **{edges}** 条 · "
                    "字段级血缘 **{column_edges}** 条 · SLA 表 **{sla_tables}** 张"),
        "h_conf_sources": "来源 ",
        "h_conf_confidence": "置信度 ",
        "h_conf_edge": "- 边 ",
        "h_cycles_title": "### 环依赖（{n} 个）",
        "h_cycles_intro": "以下环路会导致调度依赖死锁或口径混乱，需要拆解：",
        "h_cycles_none": "未检测到环依赖。",
        "h_isolated_title": "### 孤立表（{n} 张，无上下游）",
        "h_isolated_intro": "既没有上游也没有下游，可能是未接入血缘或已废弃：",
        "h_isolated_none": "没有孤立表。",
        "h_more_hidden": "- …另有 {n} 张未展示",
        "h_no_downstream_title": "### 无下游表（{n} 张，可评估下线）",
        "h_no_downstream_intro": "有上游加工但没有任何消费方，建议确认后下线以节省成本：",
        "h_no_downstream_none": "没有可下线候选表。",
    },
    "en": {
        "missing_table": "table {name} not found",
        "missing_table_md": "Table `{name}` not found.",
        "agg_group": "{name} ({n} tables)",
        "agg_root": "root: {name}",
        "agg_note": ("    %% too many nodes — aggregated by layer "
                     "(original: {nodes} tables / {edges} edges)"),
        "dashed_note": "    %% dashed = heuristic / low-confidence edge",
        "mermaid_truncated": "chain too large — truncated",
        "mermaid_truncated_more": "; {n} more nodes not shown",
        "no_col_lineage": "no downstream column lineage",
        "agg_edge": "agg",
        "tree_root_suffix": " (current table)",
        "tree_truncated": ("- … (chain truncated — increase depth or "
                           "narrow the direction)"),
        "path_none": ("No lineage path found between `{src}` and `{dst}` "
                      "(both directions tried)."),
        "path_head": "`{src}` → `{dst}` — **{n}** hop(s):",
        "path_mermaid_none": "no path found",
        "sla_title": "## SLA Delay Impact: `{root}`",
        "sla_delay_suffix": " (assumed delay {hours}h)",
        "sla_no_tasks": ("No SLA or baseline tasks downstream — the delay "
                         "does not directly hit any committed output."),
        "sla_count": ("**{n}** downstream SLA/baseline task(s) affected "
                      "(sorted by distance and output time):"),
        "sla_hops": "distance (hops)",
        "sla_propagate": ("A {hours}h delay propagates along the chain above; "
                          "the closer the task and the earlier its SLA time, "
                          "the higher the breach risk — check those first."),
        "truncated_item": "- … (chain truncated)",
        "yes": "yes",
        "no": "no",
        "list_sep": ", ",
        "sla_section_none": "No SLA or baseline tasks on the chain.",
        "impact_degraded": ("Column `{root}` has no usable column-level "
                            "lineage (SQL not covered or parse-limited) — "
                            "degraded to **table-level** downstream analysis: "
                            "about {n} downstream table(s) affected."),
        "impact_none": "Column `{root}` has no known downstream column dependencies.",
        "impact_head": "Column `{root}` impacts {n} downstream column(s):",
        "report_title": "## Lineage Report: `{root}`",
        "report_missing": "Table `{root}` not found in the lineage graph.",
        "sec_graph": "### Lineage Graph",
        "sec_chain": "### Chain Overview",
        "chain_stats": ("- upstream **{up}** · downstream **{down}** "
                        "({edges} edges, direction: {direction})"),
        "sec_sla": "### SLA & Baselines",
        "sec_impact": "### Column Impact",
        "sec_summary": "### Summary",
        "h_title": "## Lineage Governance Health Report",
        "h_stats": ("- tables **{tables}** · lineage edges **{edges}** · "
                    "column edges **{column_edges}** · SLA tables **{sla_tables}**"),
        "h_conf_sources": "sources ",
        "h_conf_confidence": "confidence ",
        "h_conf_edge": "- edges ",
        "h_cycles_title": "### Dependency cycles ({n})",
        "h_cycles_intro": ("These cycles deadlock the scheduler or blur metric "
                           "definitions — break them up:"),
        "h_cycles_none": "No dependency cycles detected.",
        "h_isolated_title": "### Isolated tables ({n}, no upstream or downstream)",
        "h_isolated_intro": ("No upstream and no downstream — possibly not wired "
                             "into lineage, or already abandoned:"),
        "h_isolated_none": "No isolated tables.",
        "h_more_hidden": "- … {n} more not shown",
        "h_no_downstream_title": ("### Tables without downstream "
                                  "({n}, retirement candidates)"),
        "h_no_downstream_intro": ("Produced upstream but consumed by nothing — "
                                  "confirm and retire to save cost:"),
        "h_no_downstream_none": "No retirement candidates.",
    },
}


def _tr(lang: str) -> dict[str, str]:
    return _I18N.get(lang, _I18N["zh"])


def _labels(lang: str) -> dict[str, str]:
    return _FIELD_LABELS_EN if lang == "en" else FIELD_LABELS


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


def _render_aggregated(chain: ChainResult, lang: str = "zh") -> str:
    """Grouped view for huge chains: one node per database/layer group."""
    tr = _tr(lang)
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
        label = tr["agg_group"].format(name=html.escape(key), n=groups[key])
        if key == root_group:
            root_bit = tr["agg_root"].format(name=html.escape(chain.root))
            label = f"<b>{label}</b><br/>{root_bit}"
        lines.append(f'    {ids.get(key)}["{label}"]')
    for (gs, gd), count in sorted(edge_counts.items()):
        lines.append(f"    {ids.get(gs)} -->|{count}| {ids.get(gd)}")
    if root_group is not None:
        lines.append("    classDef root_mark stroke:#111827,stroke-width:3px")
        lines.append(f"    class {ids.get(root_group)} root_mark")
    lines.append(tr["agg_note"].format(nodes=len(chain.nodes),
                                       edges=len(chain.edges)))
    return "\n".join(lines)


def render_mermaid(
    chain: ChainResult,
    max_nodes: int = MAX_MERMAID_NODES,
    aggregate_threshold: int = AGGREGATE_THRESHOLD,
    lang: str = "zh",
) -> str:
    tr = _tr(lang)
    if chain.missing_root or not chain.nodes:
        missing = tr["missing_table"].format(name=html.escape(chain.root))
        return f'flowchart LR\n    empty["{missing}"]'

    if len(chain.nodes) > aggregate_threshold:
        return _render_aggregated(chain, lang)

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
        lines.append(tr["dashed_note"])

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
        note = tr["mermaid_truncated"]
        if hidden > 0:
            note += tr["mermaid_truncated_more"].format(n=hidden)
        lines.append(f"    %% {note}")
    return "\n".join(lines)


def render_column_mermaid(impact: ColumnImpactResult, lang: str = "zh") -> str:
    tr = _tr(lang)
    root = f"{impact.root_table}.{impact.root_column}"
    if impact.missing_root:
        missing = tr["missing_table"].format(
            name=html.escape(impact.root_table))
        return f'flowchart LR\n    empty["{missing}"]'
    if impact.degraded and impact.table_fallback:
        return render_mermaid(impact.table_fallback, lang=lang)
    if not impact.edges:
        return (f'flowchart LR\n    {mermaid_id(root)}'
                f'["{html.escape(root)}<br/>{tr["no_col_lineage"]}"]')

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
            lines.append(f"    {src} -->|{tr['agg_edge']}| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")
    if impact.truncated:
        lines.append(f"    %% {tr['mermaid_truncated']}")
    return "\n".join(lines)


def select_mermaid(
    chain: ChainResult | None,
    impact: ColumnImpactResult | None,
    max_nodes: int = MAX_MERMAID_NODES,
    prefer_impact: bool = True,
    lang: str = "zh",
) -> str:
    """Column-level graph when a usable impact result exists (and is preferred),
    else the table-level chain graph, else empty."""
    if prefer_impact and impact is not None and not impact.degraded and impact.edges:
        return render_column_mermaid(impact, lang)
    if chain is not None and not chain.missing_root:
        return render_mermaid(chain, max_nodes, lang=lang)
    return ""


def render_tree(chain: ChainResult, lang: str = "zh") -> str:
    """Markdown indented tree fallback (upstream above root, downstream below)."""
    tr = _tr(lang)
    if chain.missing_root:
        return tr["missing_table_md"].format(name=chain.root)
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
    lines.append(f"- **`{chain.root}`**{tr['tree_root_suffix']}")
    for name in downs:
        depth = chain.depth_of[name]
        node = chain.nodes.get(name)
        layer = f" ({node.layer})" if node and node.layer else ""
        sla = " ⏰SLA" if node and node.is_sla else ""
        lines.append(f"{'  ' * depth}- ⬇ `{name}`{layer}{sla}")
    if chain.truncated:
        lines.append(tr["tree_truncated"])
    return "\n".join(lines)


def render_path(path: list[str] | None, src: str, dst: str,
                graph: LineageGraph | None = None, lang: str = "zh") -> str:
    """Markdown for a src→dst path query (None = no path found)."""
    tr = _tr(lang)
    if not path:
        return tr["path_none"].format(src=src, dst=dst)
    parts = []
    for name in path:
        node = graph.get(name) if graph else None
        layer = f"({node.layer})" if node and node.layer else ""
        parts.append(f"`{name}`{layer}")
    lines = [
        tr["path_head"].format(src=path[0], dst=path[-1], n=len(path) - 1),
        "",
        " → ".join(parts),
    ]
    return "\n".join(lines)


def render_path_mermaid(path: list[str] | None,
                        graph: LineageGraph | None = None,
                        lang: str = "zh") -> str:
    if not path:
        return f'flowchart LR\n    empty["{_tr(lang)["path_mermaid_none"]}"]'
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


def render_sla_impact(impact: SlaImpactResult, lang: str = "zh") -> str:
    """Report section: downstream SLA/baseline tasks at risk."""
    tr = _tr(lang)
    labels = _labels(lang)
    if impact.missing_root:
        return tr["missing_table_md"].format(name=impact.root)
    title = tr["sla_title"].format(root=impact.root)
    if impact.delay_hours > 0:
        title += tr["sla_delay_suffix"].format(hours=f"{impact.delay_hours:g}")
    lines = [title, ""]
    if not impact.affected:
        lines.append(tr["sla_no_tasks"])
        return "\n".join(lines)
    lines.extend([
        tr["sla_count"].format(n=len(impact.affected)),
        "",
        f"| {tr['sla_hops']} | {labels['table']} | {labels['layer']} | "
        f"{labels['is_sla']} | {labels['sla_time']} | "
        f"{labels['baselines']} |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for node, hops in impact.affected:
        lines.append(
            f"| {hops} | `{node.name}` | {node.layer or '-'} | "
            f"{tr['yes'] if node.is_sla else tr['no']} | {node.sla_time or '-'} | "
            f"{tr['list_sep'].join(node.baselines) or '-'} |"
        )
    if impact.delay_hours > 0:
        lines.extend([
            "",
            tr["sla_propagate"].format(hours=f"{impact.delay_hours:g}"),
        ])
    if impact.truncated:
        lines.append(tr["truncated_item"])
    return "\n".join(lines)


_CONF_LABELS = {"high": "高", "medium": "中", "low": "低"}


def _confidence_line(stats: dict, lang: str = "zh") -> list[str]:
    tr = _tr(lang)
    sources = stats.get("edge_sources") or {}
    conf = stats.get("edge_confidence") or {}
    if not sources and not conf:
        return []
    conf_labels = _CONF_LABELS if lang == "zh" else {}
    bits = []
    if sources:
        bits.append(
            tr["h_conf_sources"]
            + " / ".join(f"{k}:{v}" for k, v in sorted(sources.items()))
        )
    if conf:
        bits.append(
            tr["h_conf_confidence"] + " / ".join(
                f"{conf_labels.get(k, k)}:{v}" for k, v in sorted(conf.items())
            )
        )
    return [tr["h_conf_edge"] + " · ".join(bits)]


def render_health(report: HealthReport, sample: int = 30,
                  lang: str = "zh") -> str:
    """Governance health-check report, localized by *lang* (zh default)."""
    tr = _tr(lang)
    stats = report.stats
    lines = [
        tr["h_title"],
        "",
        tr["h_stats"].format(
            tables=stats.get("tables", 0), edges=stats.get("edges", 0),
            column_edges=stats.get("column_edges", 0),
            sla_tables=stats.get("sla_tables", 0)),
        *_confidence_line(stats, lang),
        "",
        tr["h_cycles_title"].format(n=len(report.cycles)),
        "",
    ]
    if report.cycles:
        lines.append(tr["h_cycles_intro"])
        lines.extend(
            f"- {' → '.join(f'`{n}`' for n in cycle)}" for cycle in report.cycles
        )
    else:
        lines.append(tr["h_cycles_none"])
    lines.extend(["", tr["h_isolated_title"].format(n=len(report.isolated)), ""])
    if report.isolated:
        lines.append(tr["h_isolated_intro"])
        lines.extend(f"- `{n}`" for n in report.isolated[:sample])
        if len(report.isolated) > sample:
            lines.append(
                tr["h_more_hidden"].format(n=len(report.isolated) - sample))
    else:
        lines.append(tr["h_isolated_none"])
    lines.extend([
        "",
        tr["h_no_downstream_title"].format(n=len(report.no_downstream)),
        "",
    ])
    if report.no_downstream:
        lines.append(tr["h_no_downstream_intro"])
        lines.extend(f"- `{n}`" for n in report.no_downstream[:sample])
        if len(report.no_downstream) > sample:
            lines.append(
                tr["h_more_hidden"].format(n=len(report.no_downstream) - sample))
    else:
        lines.append(tr["h_no_downstream_none"])
    return "\n".join(lines)


def _render_sla_section(report: LineageReport, lang: str = "zh") -> str:
    tr = _tr(lang)
    labels = _labels(lang)
    if not report.sla_nodes and not report.baseline_nodes:
        return tr["sla_section_none"]
    header = (
        f"| {labels['table']} | {labels['layer']} | "
        f"{labels['is_sla']} | {labels['sla_time']} | "
        f"{labels['baselines']} |"
    )
    lines = [header, "| --- | --- | --- | --- | --- |"]
    seen: set[str] = set()
    for node in report.sla_nodes + report.baseline_nodes:
        if node.name in seen:
            continue
        seen.add(node.name)
        lines.append(
            f"| `{node.name}` | {node.layer or '-'} | "
            f"{tr['yes'] if node.is_sla else tr['no']} | {node.sla_time or '-'} | "
            f"{tr['list_sep'].join(node.baselines) or '-'} |"
        )
    return "\n".join(lines)


def _render_impact_section(impact: ColumnImpactResult, lang: str = "zh") -> str:
    tr = _tr(lang)
    root = f"{impact.root_table}.{impact.root_column}"
    if impact.missing_root:
        return tr["missing_table_md"].format(name=impact.root_table)
    if impact.degraded:
        count = len(impact.table_fallback.nodes) - 1 if impact.table_fallback else 0
        return tr["impact_degraded"].format(root=root, n=max(count, 0))
    if not impact.impacted:
        return tr["impact_none"].format(root=root)
    lines = [tr["impact_head"].format(root=root, n=len(impact.impacted)), ""]
    lines.extend(f"- `{item}`" for item in impact.impacted)
    if impact.truncated:
        lines.append(tr["truncated_item"])
    return "\n".join(lines)


def render_report(report: LineageReport, lang: str = "zh") -> str:
    tr = _tr(lang)
    stats = report.stats()
    lines = [tr["report_title"].format(root=report.root_table), ""]
    if report.chain and report.chain.missing_root:
        lines.append(tr["report_missing"].format(root=report.root_table))
        return "\n".join(lines)

    if report.mermaid:
        lines.extend([tr["sec_graph"], "", "```mermaid", report.mermaid, "```", ""])
    if report.chain:
        lines.extend([
            tr["sec_chain"],
            "",
            tr["chain_stats"].format(
                up=stats["upstream"], down=stats["downstream"],
                edges=stats["edges"], direction=report.direction),
            "",
            render_tree(report.chain, lang),
            "",
        ])
    lines.extend([tr["sec_sla"], "", _render_sla_section(report, lang), ""])
    if report.column_impact:
        lines.extend([
            tr["sec_impact"],
            "",
            _render_impact_section(report.column_impact, lang),
            "",
        ])
    if report.summary:
        lines.extend([tr["sec_summary"], "", report.summary, ""])
    return "\n".join(lines).rstrip() + "\n"
