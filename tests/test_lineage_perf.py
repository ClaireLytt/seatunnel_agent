# -*- coding: utf-8 -*-
"""path_between 正确性回归 + 大图性能冒烟（parent 指针 BFS）。"""

from __future__ import annotations

import time

from seatunnel_agent.data_lineage.graph import LineageGraph


def _chain_graph() -> LineageGraph:
    g = LineageGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    return g


def test_path_between_full_chain():
    g = _chain_graph()
    assert g.path_between("a", "d") == ["a", "b", "c", "d"]


def test_path_between_reverse_fallback():
    g = _chain_graph()
    # d→a 无向前路径，回退到 a→d
    assert g.path_between("d", "a") == ["a", "b", "c", "d"]


def test_path_between_unreachable_returns_none():
    g = _chain_graph()
    g.add_edge("x", "y")
    assert g.path_between("a", "y") is None


def test_path_between_same_node():
    g = _chain_graph()
    assert g.path_between("a", "a") == ["a"]


def test_path_between_deterministic_shortest():
    g = LineageGraph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    # b、c 同层，sorted 顺序下 b 先扩展
    assert g.path_between("a", "d") == ["a", "b", "d"]


def test_path_between_respects_max_depth():
    g = _chain_graph()
    # a→d 需要 3 条边，max_depth=2 时不可达
    assert g.path_between("a", "d", max_depth=2) is None
    assert g.path_between("a", "c", max_depth=2) == ["a", "b", "c"]


def _wide_graph(layers: int = 50, width: int = 100) -> LineageGraph:
    """~5000 节点分层图，每个节点连到下一层的 3 个节点。"""
    g = LineageGraph()
    for layer in range(layers - 1):
        for j in range(width):
            src = f"db.l{layer:02d}_n{j:03d}"
            for off in (0, 1, 7):
                dst = f"db.l{layer + 1:02d}_n{(j + off) % width:03d}"
                g.add_edge(src, dst)
    return g


def test_large_graph_traversal_smoke():
    g = _wide_graph()
    assert len(g.nodes) == 5000

    start = time.perf_counter()
    path = g.path_between("db.l00_n000", "db.l49_n000", max_depth=60)
    downstream = g.downstream_of("db.l00_n000", depth=10, max_nodes=10000)
    elapsed = time.perf_counter() - start

    assert path is not None
    assert path[0] == "db.l00_n000"
    assert path[-1] == "db.l49_n000"
    assert len(path) == 50  # 逐层最短路径
    assert downstream.downstream_count > 0
    assert elapsed < 5.0, f"大图遍历耗时 {elapsed:.2f}s，超过 5s 阈值"


def test_large_graph_unreachable_none():
    g = _wide_graph()
    g.add_node("db.isolated")
    assert g.path_between("db.l00_n000", "db.isolated", max_depth=60) is None
