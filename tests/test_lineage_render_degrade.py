# -*- coding: utf-8 -*-
"""Mermaid 大图聚合降级测试（render.py AGGREGATE_THRESHOLD）。"""

from __future__ import annotations

from seatunnel_agent.data_lineage.graph import ChainResult, EdgeMeta, TableNode
from seatunnel_agent.data_lineage.render import AGGREGATE_THRESHOLD, render_mermaid


def _node(name: str, database: str = "", layer: str = "") -> TableNode:
    return TableNode(name=name, database=database, layer=layer)


def _big_chain(per_db: int = 60, dbs: tuple[str, ...] = ("ods_db", "dwd_db", "ads_db")) -> ChainResult:
    """>150 节点的三库链：ods_db 全部指向 dwd_db 首表，dwd_db 首表指向 ads_db 全部。"""
    chain = ChainResult(root=f"{dbs[0]}.t0", direction="both")
    for db in dbs:
        for i in range(per_db):
            name = f"{db}.t{i}"
            chain.nodes[name] = _node(name, database=db)
            chain.depth_of[name] = 0
    hub = f"{dbs[1]}.t0"
    for i in range(per_db):
        chain.edges.append((f"{dbs[0]}.t{i}", hub))
        chain.edges.append((hub, f"{dbs[2]}.t{i}"))
    return chain


def test_small_chain_not_aggregated():
    chain = ChainResult(root="a.t1", direction="both")
    for name in ("a.t1", "a.t2", "b.t3"):
        chain.nodes[name] = _node(name, database=name.split(".")[0])
        chain.depth_of[name] = 0
    chain.edges = [("a.t1", "a.t2"), ("a.t2", "b.t3")]
    out = render_mermaid(chain)
    assert "a.t1" in out
    assert "a.t2" in out
    assert "聚合" not in out
    assert "-->|" not in out


def test_big_chain_aggregates_to_group_nodes():
    chain = _big_chain()
    assert len(chain.nodes) > AGGREGATE_THRESHOLD
    out = render_mermaid(chain)
    # 每组一个节点，label 带表数量
    assert "ods_db（60 张表）" in out
    assert "dwd_db（60 张表）" in out
    assert "ads_db（60 张表）" in out
    # 逐表节点不再出现（除根表在组 label 中列出）
    assert "ods_db.t5" not in out
    assert "%% 节点过多已聚合为分层视图（原始 180 表 / 120 边）" in out


def test_aggregated_edge_counts():
    chain = _big_chain()
    out = render_mermaid(chain)
    # ods_db→dwd_db 60 条原始边聚成一条，label 标边数；dwd_db→ads_db 同理
    assert out.count("-->|60|") == 2


def test_root_group_highlighted_and_lists_root():
    chain = _big_chain()
    out = render_mermaid(chain)
    assert "<b>ods_db（60 张表）</b><br/>根表: ods_db.t0" in out
    assert "classDef root_mark" in out
    assert "class ods_db root_mark" in out


def test_group_key_falls_back_to_layer_then_other():
    chain = _big_chain()
    # 覆盖一部分节点：无 database 有 layer → 按 layer 分组；两者皆无 → other
    for i in range(10):
        name = f"ads_db.t{i}"
        chain.nodes[name] = _node(name, database="", layer="ads")
    for i in range(10, 20):
        name = f"ads_db.t{i}"
        chain.nodes[name] = _node(name)
    out = render_mermaid(chain)
    assert "ads（10 张表）" in out
    assert "other（10 张表）" in out
    assert "ads_db（40 张表）" in out


def test_threshold_override_parameter():
    chain = ChainResult(root="a.t1", direction="both")
    for name in ("a.t1", "a.t2", "b.t3"):
        chain.nodes[name] = _node(name, database=name.split(".")[0])
        chain.depth_of[name] = 0
    chain.edges = [("a.t1", "a.t2"), ("a.t2", "b.t3")]
    out = render_mermaid(chain, aggregate_threshold=2)
    assert "a（2 张表）" in out
    assert "b（1 张表）" in out
    assert "-->|1|" in out
    assert "节点过多已聚合为分层视图" in out


def test_low_confidence_dashes_still_work_below_threshold():
    chain = ChainResult(root="a.t1", direction="both")
    for name in ("a.t1", "a.t2"):
        chain.nodes[name] = _node(name, database="a")
        chain.depth_of[name] = 0
    chain.edges = [("a.t1", "a.t2")]
    chain.edge_meta[("a.t1", "a.t2")] = EdgeMeta(sources={"seatunnel"}, confidence="medium")
    out = render_mermaid(chain)
    assert "-.->" in out
    assert "%% 虚线 = 启发式/低置信度血缘边" in out
