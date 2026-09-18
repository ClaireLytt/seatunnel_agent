# -*- coding: utf-8 -*-
"""Incremental (per-file cached) SQL directory builds."""

from __future__ import annotations

import json
import os

import pytest

from seatunnel_agent.data_lineage import loaders
from seatunnel_agent.data_lineage.cache import file_cache_dir
from seatunnel_agent.data_lineage.loaders import from_sql_dir

SQL_A = "INSERT INTO dwd.orders SELECT id, amount FROM ods.orders_raw;"
SQL_B = "INSERT INTO dws.gmv SELECT amount FROM dwd.orders;"


@pytest.fixture()
def sql_dir(tmp_path):
    d = tmp_path / "sql"
    d.mkdir()
    (d / "a.sql").write_text(SQL_A, encoding="utf-8")
    (d / "b.sql").write_text(SQL_B, encoding="utf-8")
    return d


@pytest.fixture()
def cache_base(tmp_path):
    return tmp_path / "cache_root"


@pytest.fixture()
def parse_counter(monkeypatch):
    calls = {"n": 0}
    original = loaders._load_sql_script

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(loaders, "_load_sql_script", counting)
    return calls


def _graph_signature(graph):
    return (
        graph.stats(),
        {k: sorted(v) for k, v in graph.downstream.items()},
        sorted(
            (e.src_table, e.src_column, e.dst_table, e.dst_column)
            for edges in graph.column_down.values()
            for e in edges
        ),
    )


def test_first_build_writes_fragment_cache(sql_dir, cache_base, monkeypatch):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    graph, warnings = from_sql_dir(sql_dir, cache_base=cache_base)
    assert warnings == []
    assert "dwd.orders" in graph.nodes
    assert "dws.gmv" in graph.downstream.get("dwd.orders", set())
    fragments = list(file_cache_dir(cache_base).glob("*.json"))
    assert len(fragments) == 2
    doc = json.loads(fragments[0].read_text(encoding="utf-8"))
    assert "mtime_ns" in doc and "size" in doc


def test_second_build_hits_cache_and_matches(sql_dir, cache_base, monkeypatch, parse_counter):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    first, _ = from_sql_dir(sql_dir, cache_base=cache_base)
    assert parse_counter["n"] == 2
    second, warnings = from_sql_dir(sql_dir, cache_base=cache_base)
    assert warnings == []
    assert parse_counter["n"] == 2  # 全部命中缓存，未重新解析
    assert _graph_signature(second) == _graph_signature(first)


def test_modified_file_is_reparsed(sql_dir, cache_base, monkeypatch, parse_counter):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    from_sql_dir(sql_dir, cache_base=cache_base)
    path = sql_dir / "b.sql"
    path.write_text(
        "INSERT INTO dws.gmv_daily SELECT amount, pt FROM dwd.orders;",
        encoding="utf-8",
    )
    os.utime(path)
    graph, _ = from_sql_dir(sql_dir, cache_base=cache_base)
    assert parse_counter["n"] == 3  # 仅 b.sql 重新解析
    assert "dws.gmv_daily" in graph.downstream.get("dwd.orders", set())


def test_ttl_zero_bypasses_cache(sql_dir, cache_base, monkeypatch, parse_counter):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "0")
    from_sql_dir(sql_dir, cache_base=cache_base)
    from_sql_dir(sql_dir, cache_base=cache_base)
    assert parse_counter["n"] == 4  # 两次全量解析
    assert not file_cache_dir(cache_base).exists()


def test_corrupt_fragment_is_ignored(sql_dir, cache_base, monkeypatch):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    from_sql_dir(sql_dir, cache_base=cache_base)
    for fragment in file_cache_dir(cache_base).glob("*.json"):
        fragment.write_text("{not json", encoding="utf-8")
    graph, warnings = from_sql_dir(sql_dir, cache_base=cache_base)
    assert warnings == []
    assert "dws.gmv" in graph.downstream.get("dwd.orders", set())


def test_incremental_result_equals_full_parse(sql_dir, cache_base, monkeypatch):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "0")
    full, _ = from_sql_dir(sql_dir, cache_base=cache_base)
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    from_sql_dir(sql_dir, cache_base=cache_base)  # 预热缓存
    cached, _ = from_sql_dir(sql_dir, cache_base=cache_base)
    assert _graph_signature(cached) == _graph_signature(full)


def test_file_changed_during_parse_never_caches_stale(sql_dir, cache_base, monkeypatch):
    """缓存键取自读取内容前的 stat：读后文件被改，则该缓存条目下次必然失效。"""
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    path = sql_dir / "a.sql"
    original = loaders._load_sql_script
    state = {"mutated": False}

    def mutating(graph, sql_text, origin, store=None):
        if not state["mutated"] and origin.endswith("a.sql"):
            state["mutated"] = True
            # 模拟解析期间文件被外部修改（读后写）
            path.write_text(
                "INSERT INTO dws.changed SELECT c FROM dwd.new_src;",
                encoding="utf-8",
            )
        return original(graph, sql_text, origin, store=store)

    monkeypatch.setattr(loaders, "_load_sql_script", mutating)
    from_sql_dir(sql_dir, cache_base=cache_base)
    graph, _ = from_sql_dir(sql_dir, cache_base=cache_base)
    assert "dws.changed" in graph.downstream.get("dwd.new_src", set())
