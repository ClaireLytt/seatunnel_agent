# -*- coding: utf-8 -*-
"""Local TTL cache for graphs built from the Hive metadata lineage table.

A full-partition scan of ``zz.dwm_meta_table_lineage_df`` can take minutes, so
the built graph is serialized to ``logs/.lineage_cache/<meta_table>__<pt>.json``
and reused while fresh. TTL comes from ``LINEAGE_CACHE_TTL`` (seconds,
default 3600); ``0`` disables the cache. Everything is best-effort — a broken
cache file is ignored, never fatal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from .graph import ColumnEdge, LineageGraph

DEFAULT_CACHE_TTL = 3600
_CACHE_VERSION = 2
_UNSAFE_RE = re.compile(r"[^\w.\-]")


def atomic_write_json(path: Path, doc: dict) -> None:
    """tmp-write + rename so readers never see a half-written JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def cache_ttl() -> int:
    raw = os.getenv("LINEAGE_CACHE_TTL", "").strip()
    if not raw:
        return DEFAULT_CACHE_TTL
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_CACHE_TTL


def cache_dir(base: str | Path = "logs") -> Path:
    return Path(base) / ".lineage_cache"


def _cache_path(meta_table: str, partition: str, base: str | Path = "logs") -> Path:
    key = _UNSAFE_RE.sub("_", f"{meta_table}__{partition}")
    return cache_dir(base) / f"{key}.json"


def graph_to_dict(graph: LineageGraph) -> dict:
    return {
        "version": _CACHE_VERSION,
        "nodes": [
            {
                "name": n.name,
                "source_type": n.source_type,
                "layer": n.layer,
                "is_sla": n.is_sla,
                "sla_time": n.sla_time,
                "baselines": n.baselines,
                "origins": sorted(n.origins),
            }
            for n in graph.nodes.values()
        ],
        "edges": [
            _edge_entry(graph, src, dst)
            for src, dsts in graph.downstream.items()
            for dst in sorted(dsts)
        ],
        "column_edges": [
            [e.src_table, e.src_column, e.dst_table, e.dst_column,
             e.expression, e.is_aggregation, e.source, e.confidence]
            for edges in graph.column_down.values()
            for e in edges
        ],
    }


def _edge_entry(graph: LineageGraph, src: str, dst: str) -> list:
    meta = graph.edge_meta.get((src, dst))
    if meta is None:
        return [src, dst, [], "high"]
    return [src, dst, sorted(meta.sources), meta.confidence]


def graph_from_dict(doc: dict) -> LineageGraph:
    graph = LineageGraph()
    for n in doc.get("nodes", []):
        graph.add_node(
            n["name"],
            source_type=n.get("source_type", ""),
            layer=n.get("layer", ""),
            is_sla=n.get("is_sla", False),
            sla_time=n.get("sla_time", ""),
            baselines=n.get("baselines", []),
            origins=set(n.get("origins", [])),
        )
    for entry in doc.get("edges", []):
        src, dst = entry[0], entry[1]
        sources = entry[2] if len(entry) > 2 else []
        confidence = entry[3] if len(entry) > 3 else "high"
        graph.add_edge(src, dst, confidence=confidence)
        meta = graph.edge_meta.get((src, dst))
        if meta is not None:
            meta.sources.update(sources)
    for e in doc.get("column_edges", []):
        graph.add_column_edge(ColumnEdge(
            e[0], e[1], e[2], e[3], e[4], e[5],
            e[6] if len(e) > 6 else "",
            e[7] if len(e) > 7 else "high",
        ))
    return graph


def load_cached_graph(
    meta_table: str,
    partition: str,
    base: str | Path = "logs",
    ttl: int | None = None,
) -> LineageGraph | None:
    """The cached graph, or None when absent / expired / unreadable."""
    ttl = cache_ttl() if ttl is None else ttl
    if ttl <= 0:
        return None
    path = _cache_path(meta_table, partition, base)
    try:
        if not path.is_file() or time.time() - path.stat().st_mtime > ttl:
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("version") != _CACHE_VERSION:
            return None
        return graph_from_dict(doc)
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None


# ----------------------------------------------------------------------
# Per-file fragment cache (incremental SQL directory builds)
# ----------------------------------------------------------------------

def file_cache_dir(base: str | Path = "logs") -> Path:
    return cache_dir(base) / "files"


def _file_cache_path(path: Path, base: str | Path = "logs") -> Path:
    try:
        key_src = str(path.resolve())
    except OSError:
        key_src = str(path)
    key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
    return file_cache_dir(base) / f"{key}.json"


def load_file_fragment(
    path: Path,
    base: str | Path = "logs",
    ttl: int | None = None,
    dialect: str = "hive",
) -> LineageGraph | None:
    """Cached lineage fragment for one SQL file, or None on any miss.

    A fragment is valid only while the source file's (mtime_ns, size) match
    what was recorded at save time, on top of the usual TTL.
    """
    ttl = cache_ttl() if ttl is None else ttl
    if ttl <= 0:
        return None
    cache_path = _file_cache_path(path, base)
    try:
        if not cache_path.is_file() or time.time() - cache_path.stat().st_mtime > ttl:
            return None
        stat = path.stat()
        doc = json.loads(cache_path.read_text(encoding="utf-8"))
        if doc.get("version") != _CACHE_VERSION:
            return None
        if doc.get("mtime_ns") != stat.st_mtime_ns or doc.get("size") != stat.st_size:
            return None
        # 方言影响解析结果：老缓存没有该字段时按 hive（原有唯一行为）对待
        if doc.get("dialect", "hive") != dialect:
            return None
        return graph_from_dict(doc)
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return None


def save_file_fragment(
    graph: LineageGraph,
    path: Path,
    base: str | Path = "logs",
    stat: os.stat_result | None = None,
    dialect: str = "hive",
) -> None:
    """Best-effort write; failures never break the build.

    ``stat`` should be taken BEFORE reading the file's content: if the file
    changes between read and save, a post-parse stat would record the new
    (mtime, size) against the old content and the stale cache never expires.
    """
    if cache_ttl() <= 0:
        return
    cache_path = _file_cache_path(path, base)
    try:
        if stat is None:
            stat = path.stat()
        doc = graph_to_dict(graph)
        doc["mtime_ns"] = stat.st_mtime_ns
        doc["size"] = stat.st_size
        doc["dialect"] = dialect
        atomic_write_json(cache_path, doc)
    except OSError:
        pass


def save_cached_graph(
    graph: LineageGraph,
    meta_table: str,
    partition: str,
    base: str | Path = "logs",
) -> None:
    """Best-effort write; failures never break the build."""
    if cache_ttl() <= 0:
        return
    path = _cache_path(meta_table, partition, base)
    try:
        atomic_write_json(path, graph_to_dict(graph))
    except OSError:
        pass
