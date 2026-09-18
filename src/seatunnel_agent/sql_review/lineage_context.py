# -*- coding: utf-8 -*-
"""Lazy, process-wide access to the data-lineage graph for other agents.

The graph is built once from the directories named by the environment
variables ``LINEAGE_SQL_DIR`` (``*.sql`` scripts) and/or
``LINEAGE_SEATUNNEL_DIR`` (SeaTunnel configs) and cached at module level —
rebuilding on every tool call would parse the whole directory each time.
Missing config or a broken build degrades to a Chinese hint, never an
exception, so callers can surface it as a tool error message.
"""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..data_lineage.graph import LineageGraph

NO_CONFIG_HINT = (
    "未配置血缘目录：请设置环境变量 LINEAGE_SQL_DIR（*.sql 脚本目录）或 "
    "LINEAGE_SEATUNNEL_DIR（SeaTunnel 配置目录）后重试"
)

_lock = threading.Lock()
_cached: "LineageGraph | None" = None
_failed_hint = ""
_failed_at = 0.0

# A failed build is cached only briefly so a fixed directory (or transient
# error) gets retried instead of being poisoned for the process lifetime.
_FAILURE_RETRY_SECONDS = 60


def get_lineage_graph() -> "tuple[LineageGraph | None, str]":
    """(graph, hint) — the graph, or ``None`` plus a Chinese unavailability hint."""
    global _cached, _failed_hint, _failed_at
    with _lock:
        if _cached is not None:
            return _cached, ""
        if _failed_hint:
            if time.time() - _failed_at < _FAILURE_RETRY_SECONDS:
                return None, _failed_hint
            _failed_hint = ""
            _failed_at = 0.0
        sql_dir = os.getenv("LINEAGE_SQL_DIR", "").strip()
        st_dir = os.getenv("LINEAGE_SEATUNNEL_DIR", "").strip()
        if not sql_dir and not st_dir:
            return None, NO_CONFIG_HINT
        try:
            from ..data_lineage.loaders import build_graph

            graph, _warnings = build_graph(
                sql_dir=sql_dir or None,
                seatunnel_dir=st_dir or None,
            )
        except Exception as exc:  # noqa: BLE001 — degrade, never break the review
            _failed_hint = f"血缘图构建失败：{exc}"
            _failed_at = time.time()
            return None, _failed_hint
        if not graph.nodes:
            _failed_hint = "血缘目录中没有解析出任何表，请检查 LINEAGE_SQL_DIR / LINEAGE_SEATUNNEL_DIR 指向的目录内容"
            _failed_at = time.time()
            return None, _failed_hint
        _cached = graph
        return _cached, ""


def set_lineage_graph(graph: "LineageGraph | None") -> None:
    """Inject an already-built graph (UI wiring / tests)."""
    global _cached, _failed_hint, _failed_at
    with _lock:
        _cached = graph
        _failed_hint = ""
        _failed_at = 0.0


def reset_lineage_cache() -> None:
    global _cached, _failed_hint, _failed_at
    with _lock:
        _cached = None
        _failed_hint = ""
        _failed_at = 0.0
