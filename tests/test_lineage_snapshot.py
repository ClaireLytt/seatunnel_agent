# -*- coding: utf-8 -*-
"""Tests for lineage snapshots and change detection."""

from __future__ import annotations

import json

import pytest

import seatunnel_agent.data_lineage.snapshot as snapshot_mod
from seatunnel_agent.data_lineage.graph import LineageGraph
from seatunnel_agent.data_lineage.snapshot import (
    diff_graphs,
    list_snapshots,
    load_snapshot,
    render_diff_markdown,
    save_snapshot,
)
from seatunnel_agent.data_lineage.tools import LineageRuntime, execute_lineage_tool


def _graph(edges: list[tuple[str, str]], confidence: str = "high") -> LineageGraph:
    g = LineageGraph()
    for src, dst in edges:
        g.add_edge(src, dst, source="sql", confidence=confidence)
    return g


def test_save_list_load_roundtrip(tmp_path):
    g = _graph([("zz.ods_a", "zz.dwd_b"), ("zz.dwd_b", "zz.dws_c")])
    path = save_snapshot(g, name="release-1", base=tmp_path)
    assert path.is_file()

    entries = list_snapshots(base=tmp_path)
    assert len(entries) == 1
    assert entries[0]["file"] == path.name
    assert entries[0]["name"] == "release-1"
    assert entries[0]["tables"] == 3
    assert entries[0]["edges"] == 2

    loaded = load_snapshot(path.name, base=tmp_path)
    assert loaded is not None
    assert set(loaded.nodes) == set(g.nodes)
    assert loaded.downstream == g.downstream
    assert loaded.edge_meta[("zz.ods_a", "zz.dwd_b")].confidence == "high"

    by_name = load_snapshot("release-1", base=tmp_path)
    assert by_name is not None
    assert set(by_name.nodes) == set(g.nodes)


def test_save_snapshot_cleans_unsafe_name(tmp_path):
    g = _graph([("a", "b")])
    path = save_snapshot(g, name="../evil name/§", base=tmp_path)
    assert path.parent == snapshot_mod.snapshot_dir(tmp_path)
    assert "/" not in path.name and "\\" not in path.stem
    assert " " not in path.name


def test_diff_graphs_tables_edges_and_confidence():
    old = _graph([("zz.ods_a", "zz.dwd_b"), ("zz.dwd_b", "zz.dws_c")])
    new = LineageGraph()
    new.add_edge("zz.ods_a", "zz.dwd_b", source="sql", confidence="medium")
    new.add_edge("zz.dwd_b", "zz.ads_d", source="sql", confidence="high")

    diff = diff_graphs(old, new)
    assert diff["added_tables"] == ["zz.ads_d"]
    assert diff["removed_tables"] == ["zz.dws_c"]
    assert diff["added_edges"] == ["zz.dwd_b->zz.ads_d"]
    assert diff["removed_edges"] == ["zz.dwd_b->zz.dws_c"]
    assert diff["confidence_changes"] == [
        {"edge": "zz.ods_a->zz.dwd_b", "old": "high", "new": "medium"}
    ]
    assert "新增 1 表" in diff["summary"]

    md = render_diff_markdown(diff)
    assert "zz.ads_d" in md and "置信度变化" in md


def test_diff_graphs_no_change():
    g = _graph([("a", "b")])
    diff = diff_graphs(g, _graph([("a", "b")]))
    assert not diff["added_tables"] and not diff["removed_edges"]
    assert not diff["confidence_changes"]
    assert "无变化" in render_diff_markdown(diff)


def test_load_snapshot_blocks_path_traversal(tmp_path):
    # 快照目录外放一个格式合法的 JSON，任何穿越/绝对路径都不应读到它
    from seatunnel_agent.data_lineage.cache import graph_to_dict

    outside = tmp_path / "evil.json"
    outside.write_text(
        json.dumps(graph_to_dict(_graph([("a", "b")]))), encoding="utf-8"
    )
    base = tmp_path / "logs"
    saved = save_snapshot(_graph([("x", "y")]), name="ok", base=base)
    assert load_snapshot("..\\..\\evil.json", base=base) is None
    assert load_snapshot("../../evil.json", base=base) is None
    assert load_snapshot(str(outside), base=base) is None
    # 带目录前缀的输入按 basename 解析，仍能读到目录内的快照
    g = load_snapshot(f"whatever/{saved.name}", base=base)
    assert g is not None and "x" in g.nodes


def test_load_snapshot_tolerates_bad_files(tmp_path):
    directory = snapshot_mod.snapshot_dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / "20240101_000000__broken.json").write_text(
        "{not json", encoding="utf-8"
    )
    assert load_snapshot("broken", base=tmp_path) is None
    assert load_snapshot("missing", base=tmp_path) is None
    assert list_snapshots(base=tmp_path) == []


def test_list_snapshots_newest_first(tmp_path):
    directory = snapshot_mod.snapshot_dir(tmp_path)
    directory.mkdir(parents=True)
    for stamp in ("20240101_000000", "20250101_000000"):
        (directory / f"{stamp}__s.json").write_text(
            json.dumps({"nodes": [], "edges": [], "saved_at": stamp, "name": "s"}),
            encoding="utf-8",
        )
    entries = list_snapshots(base=tmp_path)
    assert [e["saved_at"] for e in entries] == ["20250101_000000", "20240101_000000"]


@pytest.fixture()
def _snapshot_tmp_base(tmp_path, monkeypatch):
    real_save = snapshot_mod.save_snapshot
    real_load = snapshot_mod.load_snapshot
    monkeypatch.setattr(
        snapshot_mod, "save_snapshot",
        lambda graph, name="": real_save(graph, name, base=tmp_path),
    )
    monkeypatch.setattr(
        snapshot_mod, "load_snapshot",
        lambda path_or_name: real_load(path_or_name, base=tmp_path),
    )
    return tmp_path


def test_tool_save_and_diff_snapshot(_snapshot_tmp_base):
    rt = LineageRuntime()
    result = json.loads(
        execute_lineage_tool("save_lineage_snapshot", {"name": "s1"}, rt)
    )
    assert "血缘图为空" in result["error"]

    rt.graph.add_edge("zz.ods_a", "zz.dwd_b", source="sql", confidence="high")
    result = json.loads(
        execute_lineage_tool("save_lineage_snapshot", {"name": "s1"}, rt)
    )
    assert result["success"] is True and result["file"].endswith(".json")

    rt.graph.add_edge("zz.dwd_b", "zz.dws_c", source="sql", confidence="medium")
    diff = json.loads(
        execute_lineage_tool("diff_lineage_snapshot", {"snapshot": "s1"}, rt)
    )
    assert diff["added_tables"] == ["zz.dws_c"]
    assert diff["added_edges"] == ["zz.dwd_b->zz.dws_c"]
    assert "血缘快照对比" in diff["markdown"]


def test_tool_diff_two_snapshots(_snapshot_tmp_base):
    rt = LineageRuntime()
    rt.graph.add_edge("a", "b")
    execute_lineage_tool("save_lineage_snapshot", {"name": "old"}, rt)
    rt.graph.add_edge("b", "c")
    execute_lineage_tool("save_lineage_snapshot", {"name": "new"}, rt)

    diff = json.loads(
        execute_lineage_tool(
            "diff_lineage_snapshot", {"old": "old", "new": "new"}, rt
        )
    )
    assert diff["added_tables"] == ["c"]

    err = json.loads(
        execute_lineage_tool("diff_lineage_snapshot", {"old": "old", "new": "nope"}, rt)
    )
    assert "找不到快照" in err["error"]

    err = json.loads(execute_lineage_tool("diff_lineage_snapshot", {}, rt))
    assert "请提供" in err["error"]
