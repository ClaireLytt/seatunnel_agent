"""Tests for value-level retrieval: index build (sqlite), persistence,
search semantics, and the match_tables integration."""

from __future__ import annotations

import json
import sqlite3

import pytest

from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.text2sql.values import (
    ValueIndex,
    candidate_columns,
    load_or_build,
)

_DDL = """
CREATE TABLE sales(
  order_id string COMMENT '订单ID',
  amount double COMMENT '金额',
  region string COMMENT '大区',
  status string COMMENT '订单状态',
  remark text COMMENT '备注',
  dt string COMMENT '日期'
)
COMMENT '销售明细';

CREATE TABLE big_part(
  id string COMMENT 'id',
  city string COMMENT '城市'
)
COMMENT '分区表（必须被跳过）'
PARTITIONED BY (pt string COMMENT '分区');
"""


@pytest.fixture()
def store() -> SchemaStore:
    return SchemaStore(parse_ddl(_DDL))


@pytest.fixture()
def sqlite_env(tmp_path, store):
    """(executor, store) over a real sqlite db."""
    from seatunnel_agent.text2sql.executor import DatabaseConfig, create_executor

    db = tmp_path / "v.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales(order_id TEXT, amount REAL, region TEXT, "
        "status TEXT, remark TEXT, dt TEXT)"
    )
    rows = [
        ("o1", 10.0, "华东", "已支付", "r1", "2026-03-01"),
        ("o2", 20.0, "华南", "已支付", "r2", "2026-03-01"),
        ("o3", 30.0, "华东", "已退款", "r3", "2026-03-02"),
    ]
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db))
    )
    return executor, store


def test_candidate_columns(store: SchemaStore) -> None:
    cols = candidate_columns(store.get("sales"))
    # string-typed, non-id columns only (dt is string too — kept; amount not)
    assert "region" in cols and "status" in cols and "remark" in cols
    assert "order_id" not in cols and "amount" not in cols


def test_build_skips_partitioned(sqlite_env) -> None:
    executor, store = sqlite_env
    index = ValueIndex.build(executor, store)
    assert "big_part" not in index.data
    assert set(index.data["sales"]["region"]) == {"华东", "华南"}
    assert set(index.data["sales"]["status"]) == {"已支付", "已退款"}


def test_build_drops_high_cardinality(sqlite_env) -> None:
    executor, store = sqlite_env
    index = ValueIndex.build(executor, store, max_distinct=1)
    # every sampled column has >1 distinct values -> all dropped
    assert "sales" not in index.data or "region" not in index.data.get("sales", {})


def test_save_load_roundtrip(sqlite_env, tmp_path) -> None:
    executor, store = sqlite_env
    index = ValueIndex.build(executor, store)
    path = index.save("abc123", index_dir=tmp_path)
    assert path.is_file()
    loaded = ValueIndex.load("abc123", index_dir=tmp_path)
    assert loaded is not None
    assert loaded.data == index.data
    assert ValueIndex.load("nope", index_dir=tmp_path) is None


def test_load_corrupt_returns_none(tmp_path) -> None:
    p = ValueIndex.cache_path("bad", index_dir=tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    assert ValueIndex.load("bad", index_dir=tmp_path) is None


def test_search_cjk_substring_and_ascii_token() -> None:
    index = ValueIndex(data={
        "sales": {
            "region": ("华东", "华南"),
            "channel": ("app", "web"),
        },
    })
    hits = index.search("华东地区app渠道的销售额")
    got = {(h.column, h.value) for h in hits}
    assert ("region", "华东") in got
    assert ("channel", "app") in got
    # 'web' must NOT match as a substring of an unrelated token
    assert ("channel", "web") not in got
    # "webinar" contains 'web' but is a different token
    assert index.search("webinar 销售") == []
    assert index.search("") == []


def test_match_tables_returns_value_hits(sqlite_env, monkeypatch, tmp_path) -> None:
    from seatunnel_agent.text2sql.tools import (
        Text2SQLRuntime,
        execute_text2sql_tool,
    )

    executor, store = sqlite_env
    rt = Text2SQLRuntime(
        store=store, ds_type="sqlite",
        db_config=executor.config,
    )
    # pre-built index injected directly (no cache file involved)
    rt._value_index = ValueIndex.build(executor, store)
    rt._value_index_store = store

    out = json.loads(execute_text2sql_tool(
        "match_tables", {"query": "华东地区已支付的金额"}, rt,
    ))
    hits = {(h["column"], h["value"]) for h in out.get("value_hits", [])}
    assert ("region", "华东") in hits
    assert ("status", "已支付") in hits
    assert any(c["table"] == "sales" for c in out["candidates"])
    assert "verbatim" in out["value_hits_note"].lower()


def test_value_hit_surfaces_missed_table(store) -> None:
    """A value hit on a table outside the top-5 keyword candidates appends it."""
    from seatunnel_agent.text2sql.tools import (
        Text2SQLRuntime,
        execute_text2sql_tool,
    )

    rt = Text2SQLRuntime(store=store, ds_type="sqlite")
    rt._value_index = ValueIndex(data={
        "sales": {"region": ("华东",)},
    })
    rt._value_index_store = store
    out = json.loads(execute_text2sql_tool(
        "match_tables", {"query": "华东"}, rt,
    ))
    sales = [c for c in out["candidates"] if c["table"] == "sales"]
    assert sales, out
    # either matched by keyword or appended via value_match
    assert out.get("value_hits")


def test_load_or_build_auto_sqlite(sqlite_env, tmp_path, monkeypatch) -> None:
    from seatunnel_agent.text2sql import values as values_mod
    from seatunnel_agent.text2sql.tools import Text2SQLRuntime

    executor, store = sqlite_env
    monkeypatch.setattr(values_mod, "_INDEX_DIR", tmp_path)
    rt = Text2SQLRuntime(
        store=store, ds_type="sqlite", db_config=executor.config,
    )
    index = load_or_build(rt)
    assert index is not None and len(index) > 0
    # second call hits the cache file
    index2 = load_or_build(rt)
    assert index2 is not None and index2.data == index.data

    # kill switch
    monkeypatch.setenv("T2S_VALUE_INDEX", "0")
    assert load_or_build(rt) is None


def test_load_or_build_non_sqlite_needs_optin(store, monkeypatch, tmp_path) -> None:
    from seatunnel_agent.text2sql import values as values_mod
    from seatunnel_agent.text2sql.tools import Text2SQLRuntime

    monkeypatch.setattr(values_mod, "_INDEX_DIR", tmp_path)
    monkeypatch.delenv("T2S_VALUE_INDEX", raising=False)
    rt = Text2SQLRuntime(store=store, ds_type="hive")
    assert load_or_build(rt) is None  # no cache, no opt-in -> disabled


def test_search_digit_values_need_boundaries() -> None:
    """Digit-only values must not fire on dates/numbers containing them
    (review fix)."""
    index = ValueIndex(data={"orders": {"status_code": ("2026", "01")}})
    assert index.search("2026-03-01 的订单") == []
    assert index.search("分区 20260301 的数据") == []
    hits = index.search("状态码为 2026 的订单")
    assert {(h.column, h.value) for h in hits} == {("status_code", "2026")}


def test_build_sqlserver_uses_top(store, monkeypatch) -> None:
    """SQL Server sampling must use TOP, not LIMIT (review fix)."""
    captured: list[str] = []

    class _FakeResult:
        rows = [("A",), ("B",)]

    class _FakeConfig:
        ds_type = "sqlserver"

    class _FakeExecutor:
        config = _FakeConfig()

        def run(self, sql, max_rows=0):
            captured.append(sql)
            return _FakeResult()

    index = ValueIndex.build(_FakeExecutor(), store)
    assert captured and all("TOP" in s and "LIMIT" not in s for s in captured)
    assert len(index) > 0


def test_runtime_value_index_caches_none(store, monkeypatch) -> None:
    """A None index is cached per store — no per-call rebuild attempt
    (review fix: avoids O(tables) schema hashing on every match_tables)."""
    from seatunnel_agent.text2sql.tools import Text2SQLRuntime

    calls = {"n": 0}

    def _fake_load_or_build(rt):
        calls["n"] += 1
        return None

    monkeypatch.setattr(
        "seatunnel_agent.text2sql.values.load_or_build", _fake_load_or_build,
    )
    rt = Text2SQLRuntime(store=store, ds_type="hive")
    assert rt.value_index is None
    assert rt.value_index is None
    assert calls["n"] == 1  # second access served from cache

    # store swap triggers exactly one retry
    from seatunnel_agent.text2sql.schema import SchemaStore as _SS
    rt.store = _SS([])
    assert rt.value_index is None
    assert calls["n"] == 2
