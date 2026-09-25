# -*- coding: utf-8 -*-
"""Change impact analysis: SQL diff × lineage downstream walk.

Given two lineage graphs (built from an "old" and a "new" SQL directory, or
from a git ref), detect what changed — tables, edges, and column-level
expression ("口径") changes — and walk the downstream chains to report the
blast radius. Fully deterministic: no database, no SQL execution, no LLM.

Severity model (drives the CLI --fail-on gate):
  error — a removed table/edge that still had downstream consumers in the
          old graph (breaking change)
  warn  — a column expression change on a table that has downstream
          consumers (metric drift)
  info  — pure additions, or changes with no downstream
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .graph import LineageGraph
from .snapshot import diff_graphs

LEVELS = ("error", "warn", "info")

_WS_RE = re.compile(r"\s+")


def _norm_expr(expr: str) -> str:
    """Normalize an expression for comparison: case/whitespace-insensitive."""
    return _WS_RE.sub(" ", (expr or "").strip()).lower()


@dataclass
class ColumnChange:
    """One column-level lineage change."""
    kind: str            # added | removed | modified
    src_table: str
    src_column: str
    dst_table: str
    dst_column: str
    old_expression: str = ""
    new_expression: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": f"{self.src_table}.{self.src_column}",
            "target": f"{self.dst_table}.{self.dst_column}",
            "old_expression": self.old_expression,
            "new_expression": self.new_expression,
        }


@dataclass
class ChangedTable:
    """One affected target table with its reasons and blast radius."""
    table: str
    level: str                                   # error | warn | info
    column_changes: list[ColumnChange] = field(default_factory=list)
    removed_upstreams: list[str] = field(default_factory=list)
    added_upstreams: list[str] = field(default_factory=list)
    is_new: bool = False
    is_removed: bool = False
    downstream: list[tuple[str, int]] = field(default_factory=list)  # (table, depth)
    downstream_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table, "level": self.level,
            "is_new": self.is_new, "is_removed": self.is_removed,
            "column_changes": [c.to_dict() for c in self.column_changes],
            "removed_upstreams": list(self.removed_upstreams),
            "added_upstreams": list(self.added_upstreams),
            "downstream": [{"table": t, "depth": d} for t, d in self.downstream],
            "downstream_truncated": self.downstream_truncated,
        }


@dataclass
class ImpactResult:
    table_diff: dict[str, Any]                   # snapshot.diff_graphs output
    changed: list[ChangedTable]
    depth: int
    old_warnings: int = 0
    new_warnings: int = 0
    elapsed_ms: int = 0

    def counts(self) -> dict[str, int]:
        by_level = {lv: 0 for lv in LEVELS}
        blast: set[str] = set()
        for c in self.changed:
            by_level[c.level] += 1
            blast.update(t for t, _ in c.downstream)
        return {
            "changed": len(self.changed),
            "blast": len(blast - {c.table for c in self.changed}),
            **by_level,
        }

    def worst_level(self) -> str | None:
        levels = {c.level for c in self.changed}
        for lv in LEVELS:
            if lv in levels:
                return lv
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats": self.counts(),
            "depth": self.depth,
            "table_diff": self.table_diff,
            "changed": [c.to_dict() for c in self.changed],
            "old_warnings": self.old_warnings,
            "new_warnings": self.new_warnings,
            "elapsed_ms": self.elapsed_ms,
        }


def _col_edge_map(graph: LineageGraph) -> dict[tuple[str, str, str, str], Any]:
    out: dict[tuple[str, str, str, str], Any] = {}
    for edges in graph.column_down.values():
        for e in edges:
            out[(e.src_table, e.src_column, e.dst_table, e.dst_column)] = e
    return out


def _downstream_pairs(graph: LineageGraph, table: str,
                      depth: int) -> tuple[list[tuple[str, int]], bool]:
    chain = graph.downstream_of(table, depth=depth)
    pairs = sorted(
        ((t, d) for t, d in chain.depth_of.items() if t != table and d > 0),
        key=lambda x: (x[1], x[0]),
    )
    return pairs, chain.truncated


def analyze_impact(
    old_graph: LineageGraph,
    new_graph: LineageGraph,
    depth: int = 3,
    old_warnings: int = 0,
    new_warnings: int = 0,
) -> ImpactResult:
    """Diff two graphs and compute the per-target blast radius."""
    t0 = time.time()
    table_diff = diff_graphs(old_graph, new_graph)

    old_cols = _col_edge_map(old_graph)
    new_cols = _col_edge_map(new_graph)
    col_changes: list[ColumnChange] = []
    for quad in sorted(set(new_cols) - set(old_cols)):
        e = new_cols[quad]
        col_changes.append(ColumnChange(
            "added", *quad, new_expression=e.expression))
    for quad in sorted(set(old_cols) - set(new_cols)):
        e = old_cols[quad]
        col_changes.append(ColumnChange(
            "removed", *quad, old_expression=e.expression))
    for quad in sorted(set(old_cols) & set(new_cols)):
        o, n = old_cols[quad], new_cols[quad]
        if (_norm_expr(o.expression) != _norm_expr(n.expression)
                or o.is_aggregation != n.is_aggregation):
            col_changes.append(ColumnChange(
                "modified", *quad,
                old_expression=o.expression, new_expression=n.expression))

    # ── collect affected target tables ──
    per_table: dict[str, ChangedTable] = {}

    def entry(table: str) -> ChangedTable:
        if table not in per_table:
            per_table[table] = ChangedTable(table=table, level="info")
        return per_table[table]

    for c in col_changes:
        entry(c.dst_table).column_changes.append(c)
    for edge in table_diff["removed_edges"]:
        src, dst = edge.split("->", 1)
        entry(dst).removed_upstreams.append(src)
    for edge in table_diff["added_edges"]:
        src, dst = edge.split("->", 1)
        entry(dst).added_upstreams.append(src)
    for tbl in table_diff["added_tables"]:
        # only targets matter: a brand-new source table with no upstream of
        # its own is still listed when it feeds an added edge (handled above)
        if tbl in new_graph.upstream:
            entry(tbl).is_new = True
    for tbl in table_diff["removed_tables"]:
        if tbl in old_graph.upstream:  # was a target in the old graph
            entry(tbl).is_removed = True

    # ── blast radius + severity ──
    for c in per_table.values():
        walk_graph = old_graph if c.is_removed else new_graph
        c.downstream, c.downstream_truncated = _downstream_pairs(
            walk_graph, c.table, depth)
        has_downstream = bool(c.downstream)
        modified = any(cc.kind == "modified" for cc in c.column_changes)
        removed_cols = any(cc.kind == "removed" for cc in c.column_changes)

        if c.is_removed:
            # a target dropped entirely: breaking when anything consumed it
            c.level = "error" if has_downstream else "info"
        elif c.removed_upstreams or removed_cols:
            # this target lost an input it used to read — it breaks itself
            c.level = "error"
        elif modified:
            # metric/logic drift: only a risk when someone consumes it
            c.level = "warn" if has_downstream else "info"
        else:
            c.level = "info"  # pure additions

    changed = sorted(per_table.values(),
                     key=lambda c: (LEVELS.index(c.level), c.table))
    return ImpactResult(
        table_diff=table_diff, changed=changed, depth=depth,
        old_warnings=old_warnings, new_warnings=new_warnings,
        elapsed_ms=int((time.time() - t0) * 1000),
    )


def analyze_dirs(
    old_dir: str | Path,
    new_dir: str | Path,
    depth: int = 3,
    sql_dialect: str = "hive",
) -> ImpactResult:
    """Convenience wrapper: build both graphs from directories and analyze."""
    from .loaders import build_graph

    for label, d in (("old", old_dir), ("new", new_dir)):
        if not Path(d).is_dir():
            raise ValueError(f"{label} SQL directory not found: {d}")
    old_graph, old_warn = build_graph(
        sql_dir=old_dir, use_cache=False, sql_dialect=sql_dialect)
    new_graph, new_warn = build_graph(
        sql_dir=new_dir, use_cache=False, sql_dialect=sql_dialect)
    return analyze_impact(
        old_graph, new_graph, depth=depth,
        old_warnings=len(old_warn), new_warnings=len(new_warn),
    )


def materialize_git_ref(ref: str, sql_dir: str | Path,
                        repo_root: str | Path | None = None) -> Path:
    """Write every ``*.sql`` under *sql_dir* as of *ref* into a temp dir
    (mirrored layout) and return its path. Raises RuntimeError outside a
    git repository or on an unknown ref."""
    sql_dir = Path(sql_dir)
    cwd = str(repo_root or Path.cwd())

    def _git(git_cwd: str, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=git_cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args[:2])} failed: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout

    # ls-tree names and ``ref:path`` specs are repo-toplevel-relative, and
    # pathspecs are cwd-relative — so anchor BOTH the sql_dir and every git
    # command at the toplevel, or a CLI run from a repo subdirectory would
    # silently materialize an empty baseline.
    toplevel = Path(_git(cwd, "rev-parse", "--show-toplevel").strip())
    top = str(toplevel)
    sql_abs = (sql_dir if sql_dir.is_absolute()
               else Path(cwd) / sql_dir).resolve()
    try:
        rel = sql_abs.relative_to(toplevel.resolve()).as_posix()
    except ValueError:
        raise RuntimeError(
            f"sql dir {sql_dir} is outside the git repository {toplevel}")

    listing = _git(top, "ls-tree", "-r", "--name-only", ref, "--", rel or ".")
    tmp = Path(tempfile.mkdtemp(prefix="impact_old_"))
    try:
        written = 0
        for line in listing.splitlines():
            name = line.strip()
            if not name.lower().endswith(".sql"):
                continue
            content = _git(top, "show", f"{ref}:{name}")
            target = tmp / (Path(name).relative_to(rel) if rel else Path(name))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written += 1
        if not written:
            # not fatal (the tree may genuinely be new at this ref), but the
            # caller should be able to tell the user "everything counts as
            # added"
            (tmp / ".impact_empty_baseline").write_text(ref, encoding="utf-8")
    except BaseException:
        # never leak a half-materialized baseline on failure
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp


# ─────────────────────────── rendering ───────────────────────────

_IMPACT_I18N = {
    "zh": {
        "title": "## 变更影响分析 (old → new)",
        "stats": "**变更 {changed} 处 · 下游波及 {blast} 表 · "
                 "error {error} / warn {warn} / info {info}**",
        "no_change": "两份 SQL 的血缘完全一致 — 无影响。",
        "removed_table": "表被移除",
        "removed_upstream": "上游被移除",
        "removed_col": "字段来源被移除",
        "modified": "字段口径变更",
        "added_table": "新增表",
        "added_upstream": "新增上游",
        "added_col": "新增字段血缘",
        "downstream": "下游波及",
        "truncated": "（深度截断）",
        "warnings": "解析警告: old {old} / new {new}",
        "disclaimer": "> 建议配合数据比对页对受影响表做上线前后校验。",
    },
    "en": {
        "title": "## Change Impact Analysis (old → new)",
        "stats": "**{changed} changes · blast radius {blast} tables · "
                 "error {error} / warn {warn} / info {info}**",
        "no_change": "Lineage is identical between the two SQL trees — no impact.",
        "removed_table": "table removed",
        "removed_upstream": "upstream removed",
        "removed_col": "column source removed",
        "modified": "column expression changed",
        "added_table": "new table",
        "added_upstream": "upstream added",
        "added_col": "column lineage added",
        "downstream": "Downstream blast radius",
        "truncated": " (depth-truncated)",
        "warnings": "parse warnings: old {old} / new {new}",
        "disclaimer": ("> Verify the affected tables with the Data "
                       "Comparison page before/after the release."),
    },
}

_LEVEL_MARK = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}


def _impact_lang(lang: str) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def _headline(c: ChangedTable, t: dict[str, str]) -> str:
    if c.is_removed:
        return t["removed_table"]
    if c.removed_upstreams:
        return t["removed_upstream"]
    if any(cc.kind == "removed" for cc in c.column_changes):
        return t["removed_col"]
    if any(cc.kind == "modified" for cc in c.column_changes):
        return t["modified"]
    if c.is_new:
        return t["added_table"]
    if c.added_upstreams:
        return t["added_upstream"]
    return t["added_col"]


def render_impact_markdown(result: ImpactResult, lang: str = "zh") -> str:
    t = _IMPACT_I18N[_impact_lang(lang)]
    lines = [t["title"], "", t["stats"].format(**result.counts()), ""]
    if result.old_warnings or result.new_warnings:
        lines += [t["warnings"].format(old=result.old_warnings,
                                       new=result.new_warnings), ""]
    if not result.changed:
        lines += [t["no_change"], "", t["disclaimer"]]
        return "\n".join(lines)

    for c in result.changed:
        mark = _LEVEL_MARK.get(c.level, "•")
        lines.append(f"### {mark} [{c.level}] `{c.table}` — {_headline(c, t)}")
        for src in c.removed_upstreams:
            lines.append(f"- {t['removed_upstream']}: `{src} -> {c.table}`")
        for src in c.added_upstreams:
            lines.append(f"- {t['added_upstream']}: `{src} -> {c.table}`")
        for cc in c.column_changes:
            if cc.kind == "modified":
                lines.append(
                    f"- `{cc.dst_column}`: `{cc.old_expression or cc.src_column}`"
                    f" → `{cc.new_expression or cc.src_column}`")
            elif cc.kind == "removed":
                lines.append(f"- {t['removed_col']}: "
                             f"`{cc.src_table}.{cc.src_column}` → "
                             f"`{cc.dst_column}`")
            else:
                lines.append(f"- {t['added_col']}: "
                             f"`{cc.src_table}.{cc.src_column}` → "
                             f"`{cc.dst_column}`")
        if c.downstream:
            chain = ", ".join(f"`{tbl}` (L{d})" for tbl, d in c.downstream)
            trunc = t["truncated"] if c.downstream_truncated else ""
            lines.append(f"- {t['downstream']}: {chain}{trunc}")
        lines.append("")
    lines.append(t["disclaimer"])
    return "\n".join(lines)


def impact_to_dict(result: ImpactResult, lang: str = "zh") -> dict[str, Any]:
    data = result.to_dict()
    data["report"] = render_impact_markdown(result, lang)
    return data
