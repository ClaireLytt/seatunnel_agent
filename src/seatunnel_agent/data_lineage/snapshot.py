# -*- coding: utf-8 -*-
"""Lineage graph snapshots and change detection.

Snapshots reuse the cache serialization format and live under
``logs/.lineage_snapshots/<timestamp>__<name>.json``. Everything is
best-effort — a broken snapshot file is skipped, never fatal.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .cache import graph_from_dict, graph_to_dict
from .graph import LineageGraph

_UNSAFE_RE = re.compile(r"[^\w.\-]")
_DEFAULT_NAME = "snapshot"


def snapshot_dir(base: str | Path = "logs") -> Path:
    return Path(base) / ".lineage_snapshots"


def _safe_name(name: str) -> str:
    cleaned = _UNSAFE_RE.sub("_", (name or "").strip())
    return cleaned or _DEFAULT_NAME


def save_snapshot(
    graph: LineageGraph, name: str = "", base: str | Path = "logs"
) -> Path:
    directory = snapshot_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe = _safe_name(name)
    path = directory / f"{stamp}__{safe}.json"
    counter = 1
    while path.exists():
        path = directory / f"{stamp}__{safe}_{counter}.json"
        counter += 1
    doc = graph_to_dict(graph)
    doc["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    doc["name"] = _safe_name(name) if name.strip() else ""
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def list_snapshots(base: str | Path = "logs") -> list[dict[str, Any]]:
    """Newest first; unreadable files are skipped."""
    directory = snapshot_dir(base)
    if not directory.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            entries.append({
                "file": path.name,
                "name": doc.get("name", ""),
                "saved_at": doc.get("saved_at", ""),
                "tables": len(doc.get("nodes", [])),
                "edges": len(doc.get("edges", [])),
            })
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return entries


def load_snapshot(
    path_or_name: str, base: str | Path = "logs"
) -> LineageGraph | None:
    """Load by file name or snapshot name (latest match wins).

    Only files inside the snapshot directory are readable: directory
    components in the input are stripped, so ``..`` traversal and absolute
    paths never escape it (the value may come from an API request).
    """
    raw = (path_or_name or "").strip()
    if not raw:
        return None
    name = Path(raw.replace("\\", "/")).name
    if not name or name in (".", ".."):
        return None
    directory = snapshot_dir(base)
    candidates: list[Path] = []
    direct = directory / name
    if direct.is_file():
        candidates.append(direct)
    else:
        for p in sorted(directory.glob("*.json"), reverse=True):
            stem_name = p.stem.split("__", 1)[-1]
            if stem_name == _safe_name(name):
                candidates.append(p)
                break
    for path in candidates:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            return graph_from_dict(doc)
        except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
    return None


def _edge_set(graph: LineageGraph) -> set[tuple[str, str]]:
    return {
        (src, dst)
        for src, dsts in graph.downstream.items()
        for dst in dsts
    }


def _confidence(graph: LineageGraph, edge: tuple[str, str]) -> str:
    meta = graph.edge_meta.get(edge)
    return meta.confidence if meta is not None else "high"


def diff_graphs(old: LineageGraph, new: LineageGraph) -> dict[str, Any]:
    old_tables = set(old.nodes)
    new_tables = set(new.nodes)
    old_edges = _edge_set(old)
    new_edges = _edge_set(new)
    confidence_changes = []
    for src, dst in sorted(old_edges & new_edges):
        before = _confidence(old, (src, dst))
        after = _confidence(new, (src, dst))
        if before != after:
            confidence_changes.append(
                {"edge": f"{src}->{dst}", "old": before, "new": after}
            )
    diff = {
        "added_tables": sorted(new_tables - old_tables),
        "removed_tables": sorted(old_tables - new_tables),
        "added_edges": sorted(f"{s}->{d}" for s, d in new_edges - old_edges),
        "removed_edges": sorted(f"{s}->{d}" for s, d in old_edges - new_edges),
        "confidence_changes": confidence_changes,
    }
    diff["summary"] = (
        f"新增 {len(diff['added_tables'])} 表 / {len(diff['added_edges'])} 边，"
        f"移除 {len(diff['removed_tables'])} 表 / {len(diff['removed_edges'])} 边，"
        f"{len(confidence_changes)} 条边置信度变化"
    )
    return diff


def render_diff_markdown(diff: dict[str, Any]) -> str:
    lines = ["## 血缘快照对比", "", f"**{diff.get('summary', '')}**"]
    sections = [
        ("added_tables", "新增表"),
        ("removed_tables", "移除表"),
        ("added_edges", "新增边"),
        ("removed_edges", "移除边"),
    ]
    for key, label in sections:
        items = diff.get(key) or []
        if items:
            lines.append(f"\n### {label}（{len(items)}）")
            lines.extend(f"- `{item}`" for item in items[:50])
            if len(items) > 50:
                lines.append(f"- …（其余 {len(items) - 50} 条省略）")
    changes = diff.get("confidence_changes") or []
    if changes:
        lines.append(f"\n### 置信度变化（{len(changes)}）")
        lines.extend(
            f"- `{c['edge']}`：{c['old']} → {c['new']}" for c in changes[:50]
        )
    if not any(diff.get(k) for k, _ in sections) and not changes:
        lines.append("\n无变化。")
    return "\n".join(lines)
