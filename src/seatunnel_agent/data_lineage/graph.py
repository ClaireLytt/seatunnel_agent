"""In-memory global lineage graph: tables as nodes, dataflow as edges.

Pure data structure — no LLM, no I/O. Populated by ``loaders`` from either
the Hive metadata lineage table or parsed SQL files, then queried for
upstream/downstream chains and column-level impact analysis.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

MAX_DEPTH = 10
MAX_NODES = 200

# Display labels use the Chinese comments from zz.dwm_meta_table_lineage_df.
FIELD_LABELS = {
    "source_type": "类型",
    "database": "库名",
    "table": "表名",
    "layer": "表分层",
    "is_sla": "是否在SLA",
    "sla_time": "SLA产出时间",
    "baselines": "所在基线",
}


def norm_table(name: str) -> str:
    """Normalize a table reference so both loaders produce mergeable keys."""
    return name.replace("`", "").replace('"', "").strip().lower()


_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass
class EdgeMeta:
    """Provenance of a table-level edge: which loaders produced it and how
    trustworthy the extraction was (sql AST=high, seatunnel cross-product=
    medium, regex fallback=low)."""

    sources: set[str] = field(default_factory=set)
    confidence: str = "high"

    def update(self, source: str, confidence: str) -> None:
        if source:
            self.sources.add(source)
        if _CONF_RANK.get(confidence, 2) > _CONF_RANK.get(self.confidence, 2):
            self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        return {"sources": sorted(self.sources), "confidence": self.confidence}


@dataclass
class TableNode:
    name: str
    source_type: str = ""
    database: str = ""
    table: str = ""
    layer: str = ""
    is_sla: bool = False
    sla_time: str = ""
    baselines: list[str] = field(default_factory=list)
    origins: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            FIELD_LABELS["source_type"]: self.source_type,
            FIELD_LABELS["database"]: self.database,
            FIELD_LABELS["table"]: self.table,
            FIELD_LABELS["layer"]: self.layer,
            FIELD_LABELS["is_sla"]: "是" if self.is_sla else "否",
            FIELD_LABELS["sla_time"]: self.sla_time,
            FIELD_LABELS["baselines"]: self.baselines,
            "origins": sorted(self.origins),
        }


@dataclass
class ColumnEdge:
    src_table: str
    src_column: str
    dst_table: str
    dst_column: str
    expression: str = ""
    is_aggregation: bool = False
    source: str = ""
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": f"{self.src_table}.{self.src_column}",
            "target": f"{self.dst_table}.{self.dst_column}",
            "expression": self.expression,
            "is_aggregation": self.is_aggregation,
            "origin": self.source,
            "confidence": self.confidence,
        }


@dataclass
class ChainResult:
    root: str
    direction: str  # "upstream" | "downstream" | "both"
    edges: list[tuple[str, str]] = field(default_factory=list)  # (up, down)
    nodes: dict[str, TableNode] = field(default_factory=dict)
    depth_of: dict[str, int] = field(default_factory=dict)
    edge_meta: dict[tuple[str, str], EdgeMeta] = field(default_factory=dict)
    truncated: bool = False
    missing_root: bool = False

    @property
    def upstream_count(self) -> int:
        return sum(
            1 for n, d in self.depth_of.items()
            if n != self.root and d < 0
        )

    @property
    def downstream_count(self) -> int:
        return sum(
            1 for n, d in self.depth_of.items()
            if n != self.root and d > 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "direction": self.direction,
            "edges": [list(e) for e in self.edges],
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "depth_of": self.depth_of,
            "edge_meta": {
                f"{s}->{d}": m.to_dict() for (s, d), m in self.edge_meta.items()
            },
            "truncated": self.truncated,
            "missing_root": self.missing_root,
        }


@dataclass
class SlaImpactResult:
    """Downstream SLA/baseline tasks reachable from a (delayed) root table."""

    root: str
    delay_hours: float = 0.0
    affected: list[tuple["TableNode", int]] = field(default_factory=list)  # (node, hops)
    missing_root: bool = False
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "delay_hours": self.delay_hours,
            "affected": [
                {**node.to_dict(), "hops": hops} for node, hops in self.affected
            ],
            "missing_root": self.missing_root,
            "truncated": self.truncated,
        }


@dataclass
class HealthReport:
    """Governance health check over the whole graph."""

    cycles: list[list[str]] = field(default_factory=list)
    isolated: list[str] = field(default_factory=list)
    no_downstream: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycles": self.cycles,
            "isolated": self.isolated,
            "no_downstream": self.no_downstream,
            "stats": self.stats,
        }


@dataclass
class ColumnImpactResult:
    root_table: str
    root_column: str
    edges: list[ColumnEdge] = field(default_factory=list)
    impacted: list[str] = field(default_factory=list)  # "table.column" in BFS order
    degraded: bool = False  # fell back to table-level downstream
    table_fallback: ChainResult | None = None
    missing_root: bool = False
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": f"{self.root_table}.{self.root_column}",
            "impacted": self.impacted,
            "edges": [e.to_dict() for e in self.edges],
            "degraded": self.degraded,
            "table_fallback": self.table_fallback.to_dict() if self.table_fallback else None,
            "missing_root": self.missing_root,
            "truncated": self.truncated,
        }


class LineageGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, TableNode] = {}
        self.downstream: dict[str, set[str]] = {}
        self.upstream: dict[str, set[str]] = {}
        self.column_down: dict[tuple[str, str], list[ColumnEdge]] = {}
        self.column_up: dict[tuple[str, str], list[ColumnEdge]] = {}
        self.edge_meta: dict[tuple[str, str], EdgeMeta] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, name: str, **attrs: Any) -> TableNode:
        """Upsert a node; never downgrade a filled attribute to empty."""
        key = norm_table(name)
        node = self.nodes.get(key)
        if node is None:
            db, _, tbl = key.rpartition(".")
            node = TableNode(name=key, database=db, table=tbl or key)
            self.nodes[key] = node
        for attr, value in attrs.items():
            if attr == "origins":
                node.origins.update(value)
            elif attr == "baselines":
                if value:
                    merged = list(node.baselines)
                    for b in value:
                        if b and b not in merged:
                            merged.append(b)
                    node.baselines = merged
            elif attr == "is_sla":
                node.is_sla = node.is_sla or bool(value)
            elif value not in ("", None):
                setattr(node, attr, value)
        return node

    def add_edge(
        self, src: str, dst: str,
        source: str = "", confidence: str = "high",
    ) -> None:
        src_key = norm_table(src)
        dst_key = norm_table(dst)
        if not src_key or not dst_key or src_key == dst_key:
            return
        self.add_node(src_key)
        self.add_node(dst_key)
        self.downstream.setdefault(src_key, set()).add(dst_key)
        self.upstream.setdefault(dst_key, set()).add(src_key)
        key = (src_key, dst_key)
        meta = self.edge_meta.get(key)
        if meta is None:
            self.edge_meta[key] = EdgeMeta(
                sources={source} if source else set(), confidence=confidence
            )
        else:
            meta.update(source, confidence)

    def add_column_edge(self, edge: ColumnEdge) -> None:
        edge.src_table = norm_table(edge.src_table)
        edge.dst_table = norm_table(edge.dst_table)
        edge.src_column = edge.src_column.strip().lower()
        edge.dst_column = edge.dst_column.strip().lower()
        if not edge.src_table or not edge.dst_table:
            return
        if not edge.src_column or not edge.dst_column:
            return
        src_key = (edge.src_table, edge.src_column)
        dst_key = (edge.dst_table, edge.dst_column)
        existing = self.column_down.setdefault(src_key, [])
        for i, e in enumerate(existing):
            if e.dst_table == edge.dst_table and e.dst_column == edge.dst_column:
                # 同一条列边重复出现时，置信度严格更高的新边替换旧边
                if _CONF_RANK.get(edge.confidence, 0) > _CONF_RANK.get(e.confidence, 0):
                    existing[i] = edge
                    ups = self.column_up.setdefault(dst_key, [])
                    for j, u in enumerate(ups):
                        if u is e:
                            ups[j] = edge
                            break
                return
        existing.append(edge)
        self.column_up.setdefault(dst_key, []).append(edge)

    def merge(self, other: LineageGraph) -> None:
        for node in other.nodes.values():
            self.add_node(
                node.name,
                source_type=node.source_type,
                layer=node.layer,
                is_sla=node.is_sla,
                sla_time=node.sla_time,
                baselines=node.baselines,
                origins=node.origins,
            )
        for src, dsts in other.downstream.items():
            for dst in dsts:
                meta = other.edge_meta.get((norm_table(src), norm_table(dst)))
                if meta is not None:
                    self.add_edge(src, dst, confidence=meta.confidence)
                    my_meta = self.edge_meta[(norm_table(src), norm_table(dst))]
                    my_meta.sources.update(meta.sources)
                else:
                    self.add_edge(src, dst)
        for edges in other.column_down.values():
            for e in edges:
                self.add_column_edge(ColumnEdge(
                    e.src_table, e.src_column, e.dst_table, e.dst_column,
                    e.expression, e.is_aggregation, e.source, e.confidence,
                ))

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> TableNode | None:
        key = norm_table(name)
        node = self.nodes.get(key)
        if node is not None:
            return node
        if "." not in key:
            matches = [n for k, n in self.nodes.items() if k.endswith(f".{key}")]
            if len(matches) == 1:
                return matches[0]
        return None

    def search(self, keyword: str, limit: int = 20) -> list[TableNode]:
        kw = keyword.strip().lower()
        if not kw:
            return []
        return [n for k, n in sorted(self.nodes.items()) if kw in k][:limit]

    def stats(self) -> dict[str, Any]:
        edge_count = sum(len(v) for v in self.downstream.values())
        column_edge_count = sum(len(v) for v in self.column_down.values())
        layers: dict[str, int] = {}
        for node in self.nodes.values():
            layer = node.layer or "unknown"
            layers[layer] = layers.get(layer, 0) + 1
        edge_sources: dict[str, int] = {}
        confidence: dict[str, int] = {}
        for meta in self.edge_meta.values():
            for s in meta.sources:
                edge_sources[s] = edge_sources.get(s, 0) + 1
            confidence[meta.confidence] = confidence.get(meta.confidence, 0) + 1
        return {
            "tables": len(self.nodes),
            "edges": edge_count,
            "column_edges": column_edge_count,
            "sla_tables": sum(1 for n in self.nodes.values() if n.is_sla),
            "layers": layers,
            "edge_sources": edge_sources,
            "edge_confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def trace(
        self,
        table: str,
        direction: str = "both",
        depth: int = 3,
        max_nodes: int = MAX_NODES,
    ) -> ChainResult:
        """BFS the chain around ``table``. Cycle-safe via visited set.

        ``depth_of`` uses negative depths for upstream, positive for downstream.
        """
        root_node = self.get(table)
        root = root_node.name if root_node else norm_table(table)
        result = ChainResult(root=root, direction=direction)
        if root_node is None:
            result.missing_root = True
            return result

        depth = max(1, min(depth, MAX_DEPTH))
        result.nodes[root] = root_node
        result.depth_of[root] = 0

        directions: list[tuple[dict[str, set[str]], int]] = []
        if direction in ("downstream", "both"):
            directions.append((self.downstream, 1))
        if direction in ("upstream", "both"):
            directions.append((self.upstream, -1))

        for adjacency, sign in directions:
            visited = {root}
            queue: deque[tuple[str, int]] = deque([(root, 0)])
            while queue:
                current, level = queue.popleft()
                if abs(level) >= depth:
                    if adjacency.get(current):
                        result.truncated = True
                    continue
                for neighbor in sorted(adjacency.get(current, ())):
                    if sign > 0:
                        result.edges.append((current, neighbor))
                    else:
                        result.edges.append((neighbor, current))
                    if neighbor in visited:
                        continue
                    if len(result.nodes) >= max_nodes:
                        result.truncated = True
                        continue
                    visited.add(neighbor)
                    node = self.nodes.get(neighbor)
                    if node is not None:
                        result.nodes[neighbor] = node
                    result.depth_of[neighbor] = (abs(level) + 1) * sign
                    queue.append((neighbor, (abs(level) + 1) * sign))

        # Dedupe edges preserving order and drop edges pointing outside the result.
        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[str, str]] = []
        for e in result.edges:
            if e in seen:
                continue
            if e[0] not in result.nodes or e[1] not in result.nodes:
                continue
            seen.add(e)
            deduped.append(e)
            meta = self.edge_meta.get(e)
            if meta is not None:
                result.edge_meta[e] = meta
        result.edges = deduped
        return result

    def upstream_of(self, table: str, depth: int = 3,
                    max_nodes: int = MAX_NODES) -> ChainResult:
        return self.trace(table, "upstream", depth, max_nodes)

    def downstream_of(self, table: str, depth: int = 3,
                      max_nodes: int = MAX_NODES) -> ChainResult:
        return self.trace(table, "downstream", depth, max_nodes)

    def full_chain(self, table: str, up_depth: int = 3, down_depth: int = 3,
                   max_nodes: int = MAX_NODES) -> ChainResult:
        up = self.trace(table, "upstream", up_depth, max_nodes)
        down = self.trace(table, "downstream", down_depth, max_nodes)
        merged = ChainResult(
            root=up.root,
            direction="both",
            truncated=up.truncated or down.truncated,
            missing_root=up.missing_root,
        )
        merged.nodes.update(up.nodes)
        merged.nodes.update(down.nodes)
        merged.depth_of.update(down.depth_of)
        merged.depth_of.update(up.depth_of)  # upstream negatives win on overlap
        merged.depth_of[merged.root] = 0
        merged.edge_meta.update(up.edge_meta)
        merged.edge_meta.update(down.edge_meta)
        seen: set[tuple[str, str]] = set()
        for e in up.edges + down.edges:
            if e not in seen:
                seen.add(e)
                merged.edges.append(e)
        return merged

    def impact_of_column(
        self,
        table: str,
        column: str,
        depth: int = 5,
        max_nodes: int = MAX_NODES,
    ) -> ColumnImpactResult:
        """Column-level downstream impact; degrades to table-level when no
        column edges exist for the root."""
        root_node = self.get(table)
        root_table = root_node.name if root_node else norm_table(table)
        col = column.strip().lower()
        result = ColumnImpactResult(root_table=root_table, root_column=col)
        if root_node is None:
            result.missing_root = True
            return result

        depth = max(1, min(depth, MAX_DEPTH))
        start = (root_table, col)
        if start not in self.column_down:
            if start in self.column_up:
                # Known leaf column: column lineage exists but nothing consumes
                # it — a genuine empty result, not a data gap.
                return result
            result.degraded = True
            result.table_fallback = self.downstream_of(root_table, depth, max_nodes)
            return result

        visited: set[tuple[str, str]] = {start}
        queue: deque[tuple[tuple[str, str], int]] = deque([(start, 0)])
        while queue:
            current, level = queue.popleft()
            if level >= depth:
                if self.column_down.get(current):
                    result.truncated = True
                continue
            for edge in self.column_down.get(current, ()):
                dst = (edge.dst_table, edge.dst_column)
                result.edges.append(edge)
                if dst in visited:
                    continue
                if len(visited) >= max_nodes:
                    result.truncated = True
                    continue
                visited.add(dst)
                result.impacted.append(f"{dst[0]}.{dst[1]}")
                queue.append((dst, level + 1))
        return result

    def path_between(self, src: str, dst: str,
                     max_depth: int = MAX_DEPTH) -> list[str] | None:
        """BFS shortest directed path src→dst; falls back to dst→src."""
        src_node = self.get(src)
        dst_node = self.get(dst)
        if src_node is None or dst_node is None:
            return None
        for start, goal in ((src_node.name, dst_node.name),
                            (dst_node.name, src_node.name)):
            path = self._bfs_path(start, goal, max_depth)
            if path:
                return path
        return None

    def sla_impact(
        self,
        table: str,
        delay_hours: float = 0.0,
        depth: int = MAX_DEPTH,
        max_nodes: int = MAX_NODES,
    ) -> SlaImpactResult:
        """Downstream SLA/baseline tasks reachable from ``table``, ordered by
        hop distance then SLA time. ``delay_hours`` is carried through for the
        report — actual breach math needs the root's own schedule, which the
        metadata table does not record."""
        chain = self.downstream_of(table, depth, max_nodes)
        result = SlaImpactResult(
            root=chain.root,
            delay_hours=max(0.0, delay_hours),
            missing_root=chain.missing_root,
            truncated=chain.truncated,
        )
        if chain.missing_root:
            return result
        affected = [
            (node, chain.depth_of[name])
            for name, node in chain.nodes.items()
            if name != chain.root and (node.is_sla or node.baselines)
        ]
        affected.sort(key=lambda item: (item[1], item[0].sla_time or "~", item[0].name))
        result.affected = affected
        return result

    def find_cycles(self, limit: int = 10) -> list[list[str]]:
        """Directed cycles via iterative DFS (recursion-free for huge graphs).

        Returns up to ``limit`` sample cycles as node paths ending where they
        started, deduped by node set.
        """
        color: dict[str, int] = {}  # 0/absent=white, 1=gray, 2=black
        cycles: list[list[str]] = []
        seen: set[frozenset[str]] = set()
        for start in sorted(self.nodes):
            if color.get(start):
                continue
            path = [start]
            on_path = {start: 0}
            color[start] = 1
            stack = [(start, iter(sorted(self.downstream.get(start, ()))))]
            while stack:
                node, neighbors = stack[-1]
                advanced = False
                for nb in neighbors:
                    state = color.get(nb, 0)
                    if state == 0:
                        color[nb] = 1
                        on_path[nb] = len(path)
                        path.append(nb)
                        stack.append(
                            (nb, iter(sorted(self.downstream.get(nb, ()))))
                        )
                        advanced = True
                        break
                    if nb in on_path:
                        cycle = path[on_path[nb]:] + [nb]
                        key = frozenset(cycle)
                        if key not in seen:
                            seen.add(key)
                            cycles.append(cycle)
                            if len(cycles) >= limit:
                                return cycles
                if not advanced:
                    stack.pop()
                    color[node] = 2
                    on_path.pop(node, None)
                    path.pop()
        return cycles

    def isolated_tables(self) -> list[str]:
        """Tables with neither upstream nor downstream edges."""
        return sorted(
            n for n in self.nodes
            if not self.upstream.get(n) and not self.downstream.get(n)
        )

    def tables_without_downstream(self) -> list[str]:
        """Tables nobody consumes (has upstream, no downstream) — candidates
        for decommission review. Isolated tables are reported separately."""
        return sorted(
            n for n in self.nodes
            if self.upstream.get(n) and not self.downstream.get(n)
        )

    def health_check(self, cycle_limit: int = 10) -> HealthReport:
        return HealthReport(
            cycles=self.find_cycles(cycle_limit),
            isolated=self.isolated_tables(),
            no_downstream=self.tables_without_downstream(),
            stats=self.stats(),
        )

    def _bfs_path(self, start: str, goal: str, max_depth: int) -> list[str] | None:
        # Parent-pointer BFS: O(V) memory instead of storing a full path per
        # queue entry. Sorted neighbor order keeps the result deterministic.
        if start == goal:
            return [start]
        visited = {start}
        parent: dict[str, str] = {}
        queue: deque[tuple[str, int]] = deque([(start, 1)])
        while queue:
            current, length = queue.popleft()
            if length > max_depth:
                continue
            for neighbor in sorted(self.downstream.get(current, ())):
                if neighbor == goal:
                    path = [current]
                    while path[-1] != start:
                        path.append(parent[path[-1]])
                    path.reverse()
                    path.append(goal)
                    return path
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = current
                    queue.append((neighbor, length + 1))
        return None
