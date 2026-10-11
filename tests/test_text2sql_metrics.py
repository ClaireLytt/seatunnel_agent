"""Tests for the metric semantic layer: YAML parsing/validation, NL
matching, deterministic SQL expansion, and the two agent tools."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.text2sql.metrics import (
    MetricError,
    MetricStore,
    build_metric_sql,
)
from seatunnel_agent.text2sql.partition import TimeRange
from seatunnel_agent.text2sql.schema import SchemaStore
from seatunnel_agent.text2sql.tools import Text2SQLRuntime, execute_text2sql_tool
from seatunnel_agent.text2sql.validator import validate_sql

_DDL = """
CREATE TABLE dwd.dwd_trade_order_di(
  order_id string COMMENT '订单ID',
  pay_amount decimal(18,2) COMMENT '应付金额',
  order_status string COMMENT '订单状态',
  channel string COMMENT '渠道',
  province string COMMENT '省份'
)
COMMENT '交易订单明细表'
PARTITIONED BY (dt string COMMENT '分区日期yyyyMMdd');

CREATE TABLE dwd.dwd_trade_refund_di(
  refund_id string COMMENT '退款ID',
  refund_amount decimal(18,2) COMMENT '退款金额',
  channel string COMMENT '渠道',
  province string COMMENT '省份'
)
COMMENT '退款明细表'
PARTITIONED BY (dt string COMMENT '分区日期yyyyMMdd');

CREATE TABLE dwd.dws_trade_summary(
  order_id string COMMENT '订单ID',
  pay_amount decimal(18,2) COMMENT '应付金额',
  order_date string COMMENT '订单日期'
)
COMMENT '交易汇总表（非分区）';
"""

_METRICS_YAML = """
version: 1
metrics:
  - name: gmv
    display_name: GMV
    aliases: [成交总额, 交易额]
    description: 已支付订单的应付金额合计
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    dimensions: [channel, province]
    default_filters: ["order_status = 'PAID'"]
    unit: 元
    owner: 数据组
  - name: refund_amount
    display_name: 退款金额
    table: dwd.dwd_trade_refund_di
    expression: SUM(refund_amount)
    time_column: dt
    dimensions: [channel, province]
  - name: refund_rate
    display_name: 退款率
    aliases: [退款占比]
    type: ratio
    numerator: refund_amount
    denominator: gmv
    unit: '%'
"""


@pytest.fixture()
def schema_store() -> SchemaStore:
    from seatunnel_agent.text2sql.schema import parse_ddl

    return SchemaStore(parse_ddl(_DDL))


@pytest.fixture()
def metric_store(schema_store: SchemaStore) -> MetricStore:
    store, errors = MetricStore.from_text(_METRICS_YAML, schema_store)
    assert errors == []
    return store


# ----------------------------------------------------------------------
# Parsing & validation
# ----------------------------------------------------------------------


def test_parse_valid_yaml(metric_store: MetricStore) -> None:
    assert len(metric_store) == 3
    gmv = metric_store.get("gmv")
    assert gmv is not None
    assert gmv.display_name == "GMV"
    assert gmv.aliases == ("成交总额", "交易额")
    assert gmv.default_filters == ("order_status = 'PAID'",)
    rate = metric_store.get("refund_rate")
    assert rate is not None and rate.is_ratio


def test_bad_yaml_top_level() -> None:
    store, errors = MetricStore.from_text("- just\n- a list\n")
    assert len(store) == 0
    assert errors and "顶层" in errors[0]


def test_missing_name_and_bad_name() -> None:
    yaml_text = """
metrics:
  - display_name: 无名指标
  - name: BadName
    table: t
    expression: SUM(x)
"""
    store, errors = MetricStore.from_text(yaml_text)
    assert len(store) == 0
    assert any("缺少 name" in e for e in errors)
    assert any("蛇形" in e for e in errors)


def test_duplicate_name() -> None:
    yaml_text = """
metrics:
  - name: gmv
    table: t
    expression: SUM(x)
  - name: gmv
    table: t
    expression: SUM(x)
"""
    store, errors = MetricStore.from_text(yaml_text)
    assert any("重复定义" in e for e in errors)


def test_validate_unknown_table(schema_store: SchemaStore) -> None:
    yaml_text = """
metrics:
  - name: gmv
    table: dwd.no_such_table
    expression: SUM(pay_amount)
"""
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert any("白名单" in e for e in errors)
    assert store.get("gmv") is None  # invalid metric is dropped


def test_validate_unknown_column(schema_store: SchemaStore) -> None:
    yaml_text = """
metrics:
  - name: gmv
    table: dwd.dwd_trade_order_di
    expression: SUM(no_such_col)
    time_column: dt
    dimensions: [no_such_dim]
"""
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert any("no_such_col" in e for e in errors)
    assert any("no_such_dim" in e for e in errors)
    assert store.get("gmv") is None


def test_validate_ratio_refs(schema_store: SchemaStore) -> None:
    yaml_text = """
metrics:
  - name: r1
    type: ratio
    numerator: missing_a
    denominator: missing_b
"""
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert sum("未定义" in e for e in errors) == 2
    assert store.get("r1") is None


def test_ratio_referencing_ratio_rejected(schema_store: SchemaStore) -> None:
    yaml_text = _METRICS_YAML + """
  - name: meta_rate
    type: ratio
    numerator: refund_rate
    denominator: gmv
"""
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert any("必须是 additive" in e for e in errors)
    assert store.get("meta_rate") is None
    assert store.get("refund_rate") is not None  # valid ones survive


# ----------------------------------------------------------------------
# NL matching
# ----------------------------------------------------------------------


def test_match_by_cjk_alias(metric_store: MetricStore) -> None:
    matches = metric_store.match("昨天各渠道的成交总额是多少")
    assert matches and matches[0].metric.name == "gmv"


def test_match_by_english_name(metric_store: MetricStore) -> None:
    matches = metric_store.match("show me gmv by channel")
    assert matches and matches[0].metric.name == "gmv"


def test_match_ratio_alias_beats_description(metric_store: MetricStore) -> None:
    matches = metric_store.match("上周的退款率怎么样")
    assert matches and matches[0].metric.name == "refund_rate"


def test_match_no_hit(metric_store: MetricStore) -> None:
    assert metric_store.match("库存周转天数") == []


# ----------------------------------------------------------------------
# Deterministic SQL expansion
# ----------------------------------------------------------------------


def _build(metric_store, schema_store, name, **kw):
    return build_metric_sql(
        metric_store.get(name), metric_store, schema_store, **kw
    )


def test_additive_sql_shape(metric_store, schema_store) -> None:
    sql = _build(
        metric_store, schema_store, "gmv",
        dimensions=["channel"],
        time_range=TimeRange(start=date(2026, 3, 13), end=date(2026, 3, 13)),
    )
    assert sql == (
        "SELECT channel, SUM(pay_amount) AS gmv\n"
        "FROM dwd.dwd_trade_order_di\n"
        "WHERE dt = '20260313'\n"
        "  AND (order_status = 'PAID')\n"
        "GROUP BY channel"
    )


def test_additive_sql_deterministic(metric_store, schema_store) -> None:
    kw = dict(
        dimensions=["channel", "province"],
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 7)),
        extra_filters=["channel = 'app'"],
    )
    sqls = {_build(metric_store, schema_store, "gmv", **kw) for _ in range(10)}
    assert len(sqls) == 1
    sql = sqls.pop()
    assert "dt >= '20260301' AND dt <= '20260307'" in sql
    assert "(channel = 'app')" in sql


def test_additive_max_partition_fallback(metric_store, schema_store) -> None:
    sql = _build(metric_store, schema_store, "gmv", max_partition="20260320")
    assert "WHERE dt = '20260320'" in sql
    assert "GROUP BY" not in sql


def test_partitioned_time_column_requires_range(metric_store, schema_store) -> None:
    with pytest.raises(MetricError, match="分区列"):
        _build(metric_store, schema_store, "gmv")


def test_dimension_whitelist_enforced(metric_store, schema_store) -> None:
    with pytest.raises(MetricError, match="允许维度"):
        _build(
            metric_store, schema_store, "gmv",
            dimensions=["order_id"], max_partition="20260320",
        )


def test_ratio_sql_no_dims(metric_store, schema_store) -> None:
    sql = _build(metric_store, schema_store, "refund_rate", max_partition="20260320")
    assert "num.refund_amount * 1.0 / NULLIF(den.gmv, 0) AS refund_rate" in sql
    assert "CROSS JOIN" in sql


def test_ratio_sql_with_dims(metric_store, schema_store) -> None:
    sql = _build(
        metric_store, schema_store, "refund_rate",
        dimensions=["channel"], max_partition="20260320",
    )
    assert sql.startswith("SELECT den.channel, num.refund_amount")
    assert "LEFT JOIN" in sql
    assert "ON den.channel = num.channel" in sql


def test_ratio_dim_must_be_shared(metric_store, schema_store) -> None:
    with pytest.raises(MetricError, match="同时"):
        _build(
            metric_store, schema_store, "refund_rate",
            dimensions=["order_id"], max_partition="20260320",
        )


def test_generated_sql_passes_validator(metric_store, schema_store) -> None:
    for name, kw in (
        ("gmv", dict(dimensions=["channel"], max_partition="20260320")),
        ("refund_rate", dict(dimensions=["channel"], max_partition="20260320")),
        ("refund_rate", dict(max_partition="20260320")),
    ):
        sql = _build(metric_store, schema_store, name, **kw)
        result = validate_sql(sql, schema_store)
        assert result.ok, f"{name}: {result.errors}\n{sql}"


def test_iso_dates_for_non_partition_time_column(schema_store) -> None:
    yaml_text = """
metrics:
  - name: order_cnt
    table: dwd.dws_trade_summary
    expression: COUNT(order_id)
    time_column: order_date
"""
    # order_date is a normal column -> ISO date literals, no partition demand
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert errors == []
    sql = build_metric_sql(
        store.get("order_cnt"), store, schema_store,
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 2)),
    )
    assert "order_date >= '2026-03-01' AND order_date <= '2026-03-02'" in sql


def test_partitioned_table_requires_partition_time_column(schema_store) -> None:
    """A metric on a partitioned table must use the partition column as its
    time column — otherwise every generated SQL would be rejected at
    execution time for the missing partition filter."""
    yaml_text = """
metrics:
  - name: bad_time
    table: dwd.dwd_trade_order_di
    expression: COUNT(order_id)
    time_column: order_id
  - name: no_time
    table: dwd.dwd_trade_order_di
    expression: COUNT(order_id)
"""
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert sum("分区列" in e for e in errors) == 2
    assert store.get("bad_time") is None and store.get("no_time") is None


# ----------------------------------------------------------------------
# Agent tools
# ----------------------------------------------------------------------


def _runtime(schema_store, metric_store) -> Text2SQLRuntime:
    return Text2SQLRuntime(store=schema_store, metrics=metric_store)


def test_tool_match_metrics(schema_store, metric_store) -> None:
    rt = _runtime(schema_store, metric_store)
    out = json.loads(execute_text2sql_tool(
        "match_metrics", {"query": "各省份的GMV"}, rt,
    ))
    assert out["count"] >= 1
    top = out["candidates"][0]
    assert top["name"] == "gmv"
    assert top["dimensions"] == ["channel", "province"]


def test_tool_match_metrics_without_catalog(schema_store) -> None:
    rt = Text2SQLRuntime(store=schema_store)
    out = json.loads(execute_text2sql_tool(
        "match_metrics", {"query": "GMV"}, rt,
    ))
    assert out["count"] == 0
    assert "note" in out


def test_tool_build_metric_sql(schema_store, metric_store) -> None:
    rt = _runtime(schema_store, metric_store)
    out = json.loads(execute_text2sql_tool(
        "build_metric_sql",
        {
            "metric": "gmv",
            "dimensions": ["channel"],
            "start_date": "2026-03-13",
            "end_date": "20260313",
        },
        rt,
    ))
    assert out["success"] is True
    assert "dt = '20260313'" in out["sql"]


def test_tool_build_metric_sql_errors(schema_store, metric_store) -> None:
    rt = _runtime(schema_store, metric_store)
    out = json.loads(execute_text2sql_tool(
        "build_metric_sql", {"metric": "nope"}, rt,
    ))
    assert "not defined" in out["error"]

    out = json.loads(execute_text2sql_tool(
        "build_metric_sql", {"metric": "gmv", "start_date": "March 13"}, rt,
    ))
    assert "无法解析日期" in out["error"]

    out = json.loads(execute_text2sql_tool(
        "build_metric_sql", {"metric": "gmv"}, rt,
    ))
    assert "分区列" in out["error"]


# ----------------------------------------------------------------------
# Cross-module integrations (direction 7): review / skew / lineage
# ----------------------------------------------------------------------


def test_execute_sql_attaches_review_findings(sqlite_runtime) -> None:
    """Chat BI × SQL Review: static critical findings ride along the result."""
    pytest.importorskip("sqlglot")
    out = json.loads(execute_text2sql_tool(
        "execute_sql",
        {"sql": "SELECT channel FROM sales WHERE dt = '2026-03-01' "
                "AND channel = NULL"},
        sqlite_runtime,
    ))
    assert out["success"] is True  # advisory, never blocking
    cats = [f["category"] for f in out.get("review_findings", [])]
    assert "where_syntax" in cats  # the '= NULL' classic
    sev = {f["severity"] for f in out["review_findings"]}
    assert sev <= {"critical", "risk"}  # suggestions are filtered out


def test_execute_sql_attaches_skew_hints_when_slow(sqlite_runtime, monkeypatch) -> None:
    """Chat BI × skew: slow batch-engine queries get skew advice."""
    monkeypatch.setenv("T2S_SLOW_QUERY_MS", "0")  # everything counts as slow
    sqlite_runtime.ds_type = "hive"  # batch engine; executor stays sqlite
    out = json.loads(execute_text2sql_tool(
        "execute_sql",
        {"sql": "SELECT COUNT(DISTINCT order_id) AS c FROM sales "
                "WHERE dt = '2026-03-01'"},
        sqlite_runtime,
    ))
    assert out["success"] is True
    cats = [h["category"] for h in out.get("skew_hints", [])]
    assert "count_distinct" in cats

    # below threshold -> no hints
    monkeypatch.setenv("T2S_SLOW_QUERY_MS", "999999")
    sqlite_runtime.cache = type(sqlite_runtime.cache)()  # bypass result cache
    out = json.loads(execute_text2sql_tool(
        "execute_sql",
        {"sql": "SELECT COUNT(DISTINCT order_id) AS c2 FROM sales "
                "WHERE dt = '2026-03-01'"},
        sqlite_runtime,
    ))
    assert "skew_hints" not in out


def test_trace_metric_caliber_only_without_lineage_dir(
    sqlite_runtime, monkeypatch,
) -> None:
    monkeypatch.delenv("T2S_LINEAGE_SQL_DIR", raising=False)
    out = json.loads(execute_text2sql_tool(
        "trace_metric", {"metric": "gmv"}, sqlite_runtime,
    ))
    assert out["success"] is True
    assert out["sources"][0]["table"] == "sales"
    assert out["sources"][0]["expression"] == "SUM(amount)"
    assert "T2S_LINEAGE_SQL_DIR" in out["note"]
    assert "lineage" not in out


def test_trace_metric_with_lineage_upstream(
    sqlite_runtime, tmp_path, monkeypatch,
) -> None:
    """Chat BI × lineage: the upstream chain of the metric's source table."""
    pytest.importorskip("sqlglot")
    sql_dir = tmp_path / "warehouse"
    sql_dir.mkdir()
    (sql_dir / "etl_sales.sql").write_text(
        "INSERT OVERWRITE TABLE sales\n"
        "SELECT o.order_id, o.amount, o.channel, o.dt\n"
        "FROM raw_orders o JOIN dim_channel c ON o.channel = c.channel;\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("T2S_LINEAGE_SQL_DIR", str(sql_dir))
    out = json.loads(execute_text2sql_tool(
        "trace_metric", {"metric": "gmv", "depth": 3}, sqlite_runtime,
    ))
    assert out["success"] is True, out
    chain = out["lineage"][0]
    assert chain["table"] == "sales"
    upstream_tables = {u["table"] for u in chain["upstream"]}
    assert "raw_orders" in upstream_tables
    assert "dim_channel" in upstream_tables
    # graph is cached on the runtime
    assert sqlite_runtime._lineage_graph is not None

    # ratio metric traces both sides
    out = json.loads(execute_text2sql_tool(
        "trace_metric", {"metric": "aov"}, sqlite_runtime,
    ))
    assert out["success"] is True
    assert len(out["sources"]) == 2
    assert len(out["lineage"]) == 2


def test_trace_metric_unknown(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool(
        "trace_metric", {"metric": "nope"}, sqlite_runtime,
    ))
    assert "not defined" in out["error"]


# ----------------------------------------------------------------------
# REST API
# ----------------------------------------------------------------------


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.text2sql.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_list_metrics(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "metrics.yaml").write_text(_METRICS_YAML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    resp = _client().get("/api/text2sql/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    names = {m["name"] for m in data["metrics"]}
    assert names == {"gmv", "refund_amount", "refund_rate"}


def test_api_list_metrics_no_file(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    monkeypatch.chdir(tmp_path)
    resp = _client().get("/api/text2sql/metrics")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_api_metrics_query_sql_only() -> None:
    pytest.importorskip("fastapi")
    resp = _client().post("/api/text2sql/metrics/query", json={
        "metric": "gmv",
        "dimensions": ["channel"],
        "start_date": "2026-03-13",
        "schema_ddl": _DDL,
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is False
    assert "dt = '20260313'" in data["sql"]
    assert "GROUP BY channel" in data["sql"]


def test_api_metrics_query_unknown_metric() -> None:
    pytest.importorskip("fastapi")
    resp = _client().post("/api/text2sql/metrics/query", json={
        "metric": "nope",
        "schema_ddl": _DDL,
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 404


def test_api_metrics_query_bad_dimension() -> None:
    pytest.importorskip("fastapi")
    resp = _client().post("/api/text2sql/metrics/query", json={
        "metric": "gmv",
        "dimensions": ["order_id"],
        "max_partition": "20260320",
        "schema_ddl": _DDL,
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 400
    assert "允许维度" in resp.json()["detail"]


def test_api_metrics_query_execute(monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from seatunnel_agent.text2sql.executor import QueryResult
    import seatunnel_agent.text2sql.api as api_mod

    class _FakeExecutor:
        def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
            assert "SUM(pay_amount) AS gmv" in sql
            assert "LIMIT" in sql  # enforce_limit applied
            return QueryResult(
                columns=["channel", "gmv"], rows=[("app", 100.0)],
                row_count=1, truncated=False, elapsed_ms=3,
            )

    monkeypatch.setattr(api_mod, "create_executor", lambda cfg: _FakeExecutor())
    # bypass from_db by giving schema_ddl AND no db introspection:
    # _load_schema_store only calls from_db when db_config is set, so patch
    # SchemaStore.from_db too.
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
    monkeypatch.setattr(
        SchemaStore, "from_db", classmethod(lambda cls, ex: cls(parse_ddl(_DDL))),
    )

    resp = _client().post("/api/text2sql/metrics/query", json={
        "metric": "gmv",
        "dimensions": ["channel"],
        "max_partition": "20260320",
        "execute": True,
        "ds_type": "hive",
        "db_config": {"host": "example", "port": 10000, "database": "dwd"},
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is True
    assert data["rows"] == [["app", 100.0]]


def test_api_metrics_query_execute_without_db() -> None:
    pytest.importorskip("fastapi")
    resp = _client().post("/api/text2sql/metrics/query", json={
        "metric": "gmv",
        "max_partition": "20260320",
        "execute": True,
        "schema_ddl": _DDL,
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 400
    assert "db_config" in resp.json()["detail"]


# ----------------------------------------------------------------------
# Attribution analysis (M2)
# ----------------------------------------------------------------------

_SQLITE_DDL = """
CREATE TABLE sales(
  order_id string COMMENT '订单ID',
  amount double COMMENT '金额',
  channel string COMMENT '渠道',
  dt string COMMENT '日期'
)
COMMENT '销售明细';
"""

_SQLITE_METRICS = """
metrics:
  - name: gmv
    display_name: GMV
    aliases: [成交总额]
    table: sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel]
  - name: order_cnt
    display_name: 订单量
    table: sales
    expression: COUNT(order_id)
    time_column: dt
    dimensions: [channel]
  - name: aov
    display_name: 客单价
    type: ratio
    numerator: gmv
    denominator: order_cnt
"""


@pytest.fixture()
def sqlite_runtime(tmp_path):
    """A Text2SQLRuntime backed by a real sqlite db with two days of sales."""
    import sqlite3

    from seatunnel_agent.text2sql.executor import DatabaseConfig
    from seatunnel_agent.text2sql.schema import parse_ddl

    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    rows = [
        # prev day 2026-03-01: app 100 (2 orders), web 50 (1 order) -> 150
        ("o1", 60.0, "app", "2026-03-01"),
        ("o2", 40.0, "app", "2026-03-01"),
        ("o3", 50.0, "web", "2026-03-01"),
        # curr day 2026-03-02: app 80, web 70, mini 10 (new) -> 160
        ("o4", 80.0, "app", "2026-03-02"),
        ("o5", 70.0, "web", "2026-03-02"),
        ("o6", 10.0, "mini", "2026-03-02"),
    ]
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()

    schema_store = SchemaStore(parse_ddl(_SQLITE_DDL))
    metric_store, errors = MetricStore.from_text(_SQLITE_METRICS, schema_store)
    assert errors == []
    return Text2SQLRuntime(
        store=schema_store,
        metrics=metric_store,
        ds_type="sqlite",
        db_config=DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)),
    )


def test_attribution_math_pure() -> None:
    """Contribution identity on a hand-built execute_fn (no DB)."""
    from seatunnel_agent.text2sql.attribution import run_attribution
    from seatunnel_agent.text2sql.schema import parse_ddl

    schema_store = SchemaStore(parse_ddl(_SQLITE_DDL))
    store, errors = MetricStore.from_text(_SQLITE_METRICS, schema_store)
    assert errors == []

    answers = {
        # (has_dim, is_curr) -> result
        (False, False): ([("total",)], [(150.0,)]),
        (False, True): ([("total",)], [(160.0,)]),
        (True, False): (["channel", "gmv"], [("app", 100.0), ("web", 50.0)]),
        (True, True): (["channel", "gmv"], [("app", 80.0), ("web", 70.0), ("mini", 10.0)]),
    }

    def execute(sql: str):
        has_dim = "GROUP BY" in sql
        is_curr = "2026-03-02" in sql
        cols, rows = answers[(has_dim, is_curr)]
        return list(cols), rows

    result = run_attribution(
        store.get("gmv"), store, schema_store, execute,
        curr_range=TimeRange(start=date(2026, 3, 2), end=date(2026, 3, 2)),
        prev_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
    )
    assert result.prev_total == 150.0 and result.curr_total == 160.0
    assert result.delta == 10.0
    assert abs(result.change_rate - 10.0 / 150.0) < 1e-12
    assert result.sql_count == 4  # 2 totals + 2 for the single dimension

    bd = result.dimensions[0]
    assert bd.check_ok  # contributions sum exactly to the change rate
    by_value = {r.value: r for r in bd.rows}
    assert abs(by_value["app"].contribution - (-20.0 / 150.0)) < 1e-12
    assert by_value["mini"].is_new
    # sorted by |delta| desc: app(-20) and web(+20) before mini(+10)
    assert {bd.rows[0].value, bd.rows[1].value} == {"app", "web"}


def test_attribution_requires_both_ranges() -> None:
    from seatunnel_agent.text2sql.attribution import run_attribution
    from seatunnel_agent.text2sql.schema import parse_ddl

    schema_store = SchemaStore(parse_ddl(_SQLITE_DDL))
    store, _ = MetricStore.from_text(_SQLITE_METRICS, schema_store)
    with pytest.raises(MetricError, match="时间范围"):
        run_attribution(
            store.get("gmv"), store, schema_store, lambda s: ([], []),
            curr_range=TimeRange(), prev_range=TimeRange(start=date(2026, 3, 1)),
        )


def test_tool_run_attribution_sqlite(sqlite_runtime) -> None:
    """End-to-end: tool -> deterministic SQL -> sqlite -> contribution table."""
    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {
            "metric": "gmv",
            "curr_start": "2026-03-02",
            "prev_start": "2026-03-01",
        },
        sqlite_runtime,
    ))
    assert out["success"] is True, out
    assert out["type"] == "additive"
    assert out["prev_total"] == 150.0 and out["curr_total"] == 160.0
    assert out["best_dimension"] == "channel"
    top = out["dimensions"][0]["top_contributors"]
    mini = next(r for r in top if r["value"] == "mini")
    assert mini.get("is_new") is True
    # contributions sum to the change rate
    assert out["dimensions"][0]["check_ok"] is True

    # the breakdown was published as the last result for the UI
    rt = sqlite_runtime
    assert rt.last_result is not None
    assert rt.last_result.columns == ["channel", "prev", "curr", "delta", "contribution_pct"]
    assert rt.last_result.row_count == 3


def test_tool_run_attribution_ratio(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {
            "metric": "aov",
            "curr_start": "2026-03-02",
            "prev_start": "2026-03-01",
        },
        sqlite_runtime,
    ))
    assert out["success"] is True, out
    assert out["type"] == "ratio"
    # prev: 150/3 = 50; curr: 160/3 = 53.33
    assert out["prev_ratio"] == 50.0
    assert abs(out["curr_ratio"] - 160.0 / 3) < 1e-6
    assert out["numerator"]["metric"] == "gmv"
    assert out["denominator"]["metric"] == "order_cnt"


def test_tool_run_attribution_compare_mode(sqlite_runtime) -> None:
    """compare_mode derives the comparison period deterministically."""
    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02", "compare_mode": "mom"},
        sqlite_runtime,
    ))
    assert out["success"] is True, out
    # mom on a single day = the preceding day -> 03-01 vs 03-02
    assert out["prev_period"] == "2026-03-01"
    assert out["prev_total"] == 150.0 and out["curr_total"] == 160.0

    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02", "compare_mode": "weird"},
        sqlite_runtime,
    ))
    assert "compare_mode" in out["error"]

    out = json.loads(execute_text2sql_tool(
        "run_attribution", {"metric": "gmv", "curr_start": "2026-03-02"},
        sqlite_runtime,
    ))
    assert "prev_start" in out["error"] or "compare_mode" in out["error"]


def test_tool_run_attribution_export_report(sqlite_runtime, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path))  # in case exporter honors it
    from seatunnel_agent.text2sql import exporter as _exp
    monkeypatch.setattr(
        _exp, "default_desktop_dir", lambda: tmp_path, raising=False,
    )
    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02",
         "prev_start": "2026-03-01", "export_report": True},
        sqlite_runtime,
    ))
    assert out["success"] is True, out
    path = out.get("report_path", "")
    assert path.endswith(".md"), out
    text = Path(path).read_text(encoding="utf-8")
    assert "异动归因报告" in text
    assert "| app" in text  # breakdown table rows
    assert "贡献率" in text


def test_render_attribution_markdown_ratio() -> None:
    from seatunnel_agent.text2sql.attribution import (
        AttributionResult,
        render_attribution_markdown,
    )

    a = AttributionResult(
        metric="x", display_name="X", unit="元", prev_label="a", curr_label="b",
        prev_total=1, curr_total=2, delta=1, change_rate=1.0,
    )
    b = AttributionResult(
        metric="y", display_name="Y", unit="", prev_label="a", curr_label="b",
        prev_total=0, curr_total=3, delta=3, change_rate=None,
    )
    text = render_attribution_markdown([a, b], title="T")
    assert text.startswith("# T")
    assert "## X (x)" in text and "## Y (y)" in text
    assert "N/A（基期为 0）" in text


def test_metric_hybrid_ranking(sqlite_runtime) -> None:
    """match_metrics now rides the hybrid retriever (BM25 bridges words the
    alias scorer misses via expression/description tokens)."""
    out = json.loads(execute_text2sql_tool(
        "match_metrics", {"query": "成交总额怎么样"}, sqlite_runtime,
    ))
    assert out["count"] >= 1
    assert out["candidates"][0]["name"] == "gmv"
    # retriever rebuilt when metric store swaps
    first = sqlite_runtime.retriever
    sqlite_runtime.metrics = sqlite_runtime.metrics  # same -> cached
    assert sqlite_runtime.retriever is first


def test_api_key_auth(monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.api_auth import require_api_key
    from seatunnel_agent.text2sql.api import router

    app = FastAPI()
    app.include_router(router, dependencies=[Depends(require_api_key)])
    client = TestClient(app)

    monkeypatch.delenv("SEATUNNEL_API_KEY", raising=False)
    assert client.get("/api/text2sql/health").status_code == 200  # open

    monkeypatch.setenv("SEATUNNEL_API_KEY", "sekrit")
    assert client.get("/api/text2sql/health").status_code == 401
    assert client.get(
        "/api/text2sql/health", headers={"X-API-Key": "wrong"},
    ).status_code == 401
    assert client.get(
        "/api/text2sql/health", headers={"X-API-Key": "sekrit"},
    ).status_code == 200


def test_mcp_trace_and_attribution_tools(tmp_path, monkeypatch) -> None:
    import sqlite3

    from seatunnel_agent.text2sql.mcp_server import build_tool_functions

    db = tmp_path / "s.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", [
        ("o1", 150.0, "app", "2026-03-01"), ("o2", 160.0, "app", "2026-03-02"),
    ])
    conn.commit()
    conn.close()
    ddl = tmp_path / "schema.sql"
    ddl.write_text(_SQLITE_DDL, encoding="utf-8")
    metrics = tmp_path / "metrics.yaml"
    metrics.write_text(_SQLITE_METRICS, encoding="utf-8")
    monkeypatch.delenv("T2S_LINEAGE_SQL_DIR", raising=False)

    tools = build_tool_functions(
        ddl_path=str(ddl), metrics_path=str(metrics),
        ds_type="sqlite", allow_execute=True, database=str(db),
    )
    out = json.loads(tools["trace_metric"]("gmv"))
    assert out["sources"][0]["table"] == "sales"
    assert "note" in out  # lineage dir unset

    out = json.loads(tools["metric_attribution"](
        "gmv", curr_start="2026-03-02", prev_start="2026-03-01",
    ))
    assert out["type"] == "additive"
    assert out["prev_total"] == 150.0 and out["curr_total"] == 160.0

    # without allow_execute the attribution tool is absent
    tools2 = build_tool_functions(
        ddl_path=str(ddl), metrics_path=str(metrics), ds_type="sqlite",
    )
    assert "metric_attribution" not in tools2
    assert "trace_metric" in tools2


def test_unified_entry_review_sql(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool(
        "review_sql",
        {"sql": "SELECT channel FROM sales WHERE channel = NULL"},
        sqlite_runtime,
    ))
    assert out["success"] is True
    assert out["counts"].get("critical", 0) >= 1
    assert any(f["category"] == "where_syntax" for f in out["findings"])

    out = json.loads(execute_text2sql_tool(
        "review_sql", {"sql": "SELECT 1", "dialect": "martian"}, sqlite_runtime,
    ))
    assert "Unknown review dialect" in out["error"]


def test_unified_entry_skew_check(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool(
        "skew_check",
        {"sql": "SELECT COUNT(DISTINCT order_id) FROM sales", "dialect": "hive"},
        sqlite_runtime,
    ))
    assert out["success"] is True
    assert out["finding_count"] >= 1
    assert "COUNT(DISTINCT" in out["report_markdown"]


def test_unified_entry_transpile_sql(sqlite_runtime) -> None:
    pytest.importorskip("sqlglot")
    out = json.loads(execute_text2sql_tool(
        "transpile_sql",
        {"sql": "SELECT NVL(amount, 0) FROM sales",
         "source_dialect": "hive", "target_dialect": "doris"},
        sqlite_runtime,
    ))
    assert out["success"] is True, out
    assert out["dst_dialect"] == "doris"
    assert out["statements"][0]["output_sql"]

    out = json.loads(execute_text2sql_tool(
        "transpile_sql", {"sql": "SELECT 1"}, sqlite_runtime,
    ))
    assert "required" in out["error"]


def test_tool_run_attribution_truncation_guard(sqlite_runtime) -> None:
    """A drill-down hitting the row limit must fail loudly, not silently
    produce an incomplete contribution decomposition."""
    sqlite_runtime.default_limit = 2  # curr day has 3 channels
    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02", "prev_start": "2026-03-01"},
        sqlite_runtime,
    ))
    assert "error" in out
    assert "行上限" in out["error"]


def test_tool_run_attribution_errors(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool(
        "run_attribution", {"metric": "nope", "curr_start": "x", "prev_start": "y"},
        sqlite_runtime,
    ))
    assert "not defined" in out["error"]

    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02", "prev_start": ""},
        sqlite_runtime,
    ))
    assert "curr_start" in out["error"] or "prev_start" in out["error"]

    out = json.loads(execute_text2sql_tool(
        "run_attribution",
        {"metric": "gmv", "curr_start": "2026-03-02", "prev_start": "2026-03-01",
         "dimension": "order_id"},
        sqlite_runtime,
    ))
    assert "允许维度" in out["error"]


def test_api_metrics_attribution_sqlite(sqlite_runtime, monkeypatch) -> None:
    """REST attribution end-to-end on real sqlite (from_db patched — the
    sqlite introspector's full_name quirk is out of scope here)."""
    pytest.importorskip("fastapi")
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

    monkeypatch.setattr(
        SchemaStore, "from_db",
        classmethod(lambda cls, ex: cls(parse_ddl(_SQLITE_DDL))),
    )
    resp = _client().post("/api/text2sql/metrics/attribution", json={
        "metric": "gmv",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
        "ds_type": "sqlite",
        "db_config": {"database": sqlite_runtime.db_config.database},
        "metrics_yaml": _SQLITE_METRICS,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "additive"
    assert data["prev_total"] == 150.0 and data["curr_total"] == 160.0
    assert data["best_dimension"] == "channel"


def test_api_metrics_attribution_requires_db() -> None:
    pytest.importorskip("fastapi")
    resp = _client().post("/api/text2sql/metrics/attribution", json={
        "metric": "gmv",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
        "schema_ddl": _DDL,
        "metrics_yaml": _METRICS_YAML,
    })
    assert resp.status_code == 400
    assert "db_config" in resp.json()["detail"]


def test_sqlite_from_db_bare_table_names(sqlite_runtime) -> None:
    """SQLite introspection must not prefix table names with the db file
    path — that used to poison the whitelist so no SQL could ever pass."""
    from seatunnel_agent.text2sql.executor import create_executor
    from seatunnel_agent.text2sql.validator import validate_sql

    store = SchemaStore.from_db(create_executor(sqlite_runtime.db_config))
    assert store.table_names == ["sales"]
    result = validate_sql("SELECT COUNT(*) FROM sales", store)
    assert result.ok, result.errors


def test_load_metric_store_env_path(tmp_path, monkeypatch) -> None:
    target = tmp_path / "m.yaml"
    target.write_text(
        "metrics:\n  - name: x\n    table: t\n    expression: SUM(a)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("T2S_METRICS_PATH", str(target))
    from seatunnel_agent.text2sql.metrics import load_metric_store

    store, errors = load_metric_store()
    assert errors == [] and store.get("x") is not None


def test_waterfall_chart_detection_and_build() -> None:
    pytest.importorskip("matplotlib")
    from seatunnel_agent.text2sql.chart import build_chart, detect_chart_type

    columns = ["channel", "prev", "curr", "delta", "contribution_pct"]
    rows = [
        ("app", 100.0, 80.0, -20.0, -13.33),
        ("web", 50.0, 70.0, 20.0, 13.33),
        ("mini (新增)", 0.0, 10.0, 10.0, 6.67),
    ]
    assert detect_chart_type(columns, rows) == "waterfall"
    fig = build_chart(columns, rows, "waterfall")
    assert fig is not None
    import matplotlib.pyplot as plt
    plt.close(fig)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


@pytest.fixture()
def cli_files(tmp_path):
    ddl = tmp_path / "schema.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    yml = tmp_path / "metrics.yaml"
    yml.write_text(_METRICS_YAML, encoding="utf-8")
    return str(ddl), str(yml)


def _invoke(*args):
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    return CliRunner().invoke(cli, list(args))


def test_cli_metrics_validate_ok(cli_files) -> None:
    ddl, yml = cli_files
    result = _invoke("metrics", "validate", "--file", yml, "--ddl", ddl)
    assert result.exit_code == 0, result.output
    assert "校验通过" in result.output


def test_cli_metrics_validate_fails_on_bad_column(tmp_path, cli_files) -> None:
    ddl, _ = cli_files
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "metrics:\n  - name: gmv\n    table: dwd.dwd_trade_order_di\n"
        "    expression: SUM(no_such)\n",
        encoding="utf-8",
    )
    result = _invoke("metrics", "validate", "--file", str(bad), "--ddl", ddl)
    assert result.exit_code == 1
    assert "no_such" in result.output


def test_cli_metrics_list_and_show(cli_files) -> None:
    _, yml = cli_files
    result = _invoke("metrics", "list", "--file", yml)
    assert result.exit_code == 0, result.output
    assert "gmv" in result.output and "refund_rate" in result.output

    result = _invoke("metrics", "show", "gmv", "--file", yml)
    assert result.exit_code == 0, result.output
    assert "SUM(pay_amount)" in result.output

    result = _invoke("metrics", "show", "nope", "--file", yml)
    assert result.exit_code != 0


def test_cli_metrics_sql(cli_files) -> None:
    ddl, yml = cli_files
    result = _invoke(
        "metrics", "sql", "gmv", "--file", yml, "--ddl", ddl,
        "--dim", "channel", "--start", "2026-03-01", "--end", "2026-03-07",
        "--where", "channel = 'app'",
    )
    assert result.exit_code == 0, result.output
    assert "dt >= '20260301' AND dt <= '20260307'" in result.output
    assert "(channel = 'app')" in result.output

    # missing time range on a partitioned time column -> clean error
    result = _invoke("metrics", "sql", "gmv", "--file", yml, "--ddl", ddl)
    assert result.exit_code != 0
    assert "分区列" in result.output


def test_prompt_includes_metric_catalog(schema_store, metric_store) -> None:
    from seatunnel_agent.text2sql.prompts import build_text2sql_prompt

    prompt = build_text2sql_prompt(schema_store, "hive", metric_store=metric_store)
    assert "Metric Caliber Rules" in prompt
    assert "- gmv (GMV) = SUM(pay_amount) FROM dwd.dwd_trade_order_di" in prompt

    plain = build_text2sql_prompt(schema_store, "hive")
    assert "Metric Caliber Rules" not in plain


# ----------------------------------------------------------------------
# Star-schema joins (dimension tables)
# ----------------------------------------------------------------------

_JOIN_DDL = _DDL + """
CREATE TABLE dim.dim_channel(
  channel string COMMENT 'channel id',
  channel_name string COMMENT 'channel display name',
  is_deleted int COMMENT 'soft-delete flag'
)
COMMENT 'channel dimension table';

CREATE TABLE dim.dim_channel_df(
  channel string COMMENT 'channel id',
  channel_name string COMMENT 'channel display name'
)
COMMENT 'partitioned channel dim'
PARTITIONED BY (pt string COMMENT 'partition');
"""

_JOIN_YAML = """
metrics:
  - name: gmv_star
    display_name: GMV(star)
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins:
      - table: dim.dim_channel
        alias: ch
        local_key: channel
        type: left
        filters: ["is_deleted = 0"]
    dimensions: [province, ch.channel_name]
    default_filters: ["order_status = 'PAID'"]
  - name: order_cnt_star
    display_name: order count(star)
    table: dwd.dwd_trade_order_di
    expression: COUNT(order_id)
    time_column: dt
    joins:
      - table: dim.dim_channel
        alias: ch
        local_key: channel
    dimensions: [province, ch.channel_name]
  - name: aov_star
    display_name: AOV(star)
    type: ratio
    numerator: gmv_star
    denominator: order_cnt_star
"""


@pytest.fixture()
def join_schema_store() -> SchemaStore:
    from seatunnel_agent.text2sql.schema import parse_ddl

    return SchemaStore(parse_ddl(_JOIN_DDL))


@pytest.fixture()
def join_metric_store(join_schema_store: SchemaStore) -> MetricStore:
    store, errors = MetricStore.from_text(_JOIN_YAML, join_schema_store)
    assert errors == []
    return store


def test_join_parse_defaults(join_metric_store: MetricStore) -> None:
    m = join_metric_store.get("gmv_star")
    assert m is not None and len(m.joins) == 1
    spec = m.joins[0]
    assert spec.alias == "ch"
    assert spec.remote_key == "channel"  # defaults to local_key
    assert spec.join_type == "left"
    assert spec.filters == ("is_deleted = 0",)


def test_join_validation_errors(join_schema_store: SchemaStore) -> None:
    yaml_text = """
metrics:
  - name: bad_table
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins: [{table: dim.no_such, alias: x, local_key: channel}]
  - name: bad_partitioned
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins: [{table: dim.dim_channel_df, alias: x, local_key: channel}]
  - name: bad_keys
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins:
      - {table: dim.dim_channel, alias: ch, local_key: nope, remote_key: also_nope}
  - name: bad_dim_alias
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins: [{table: dim.dim_channel, alias: ch, local_key: channel}]
    dimensions: [xx.channel_name]
  - name: bad_alias_t
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    joins: [{table: dim.dim_channel, alias: t, local_key: channel}]
"""
    store, errors = MetricStore.from_text(yaml_text, join_schema_store)
    assert len(store) == 0
    joined = "\n".join(errors)
    assert "不在 schema 白名单中" in joined
    assert "分区表" in joined
    assert "local_key 'nope' 不存在于事实表" in joined
    assert "remote_key 'also_nope' 不存在于" in joined
    assert "未声明的 join 别名 'xx'" in joined
    assert "保留别名" in joined


def test_join_sql_golden(join_metric_store, join_schema_store) -> None:
    sql = build_metric_sql(
        join_metric_store.get("gmv_star"), join_metric_store, join_schema_store,
        dimensions=["ch.channel_name"],
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
        extra_filters=["province = 'GD'"],
    )
    assert sql == (
        "SELECT ch.channel_name AS channel_name, SUM(t.pay_amount) AS gmv_star\n"
        "FROM dwd.dwd_trade_order_di t\n"
        "LEFT JOIN dim.dim_channel ch ON t.channel = ch.channel AND (ch.is_deleted = 0)\n"
        "WHERE t.dt = '20260301'\n"
        "  AND (t.order_status = 'PAID')\n"
        "  AND (t.province = 'GD')\n"
        "GROUP BY ch.channel_name"
    )


def test_join_sql_no_dims_and_fact_dim(join_metric_store, join_schema_store) -> None:
    tr = TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 7))
    sql = build_metric_sql(
        join_metric_store.get("gmv_star"), join_metric_store, join_schema_store,
        time_range=tr,
    )
    assert "FROM dwd.dwd_trade_order_di t" in sql
    assert "GROUP BY" not in sql
    assert "t.dt >= '20260301' AND t.dt <= '20260307'" in sql

    sql2 = build_metric_sql(
        join_metric_store.get("gmv_star"), join_metric_store, join_schema_store,
        dimensions=["province"], time_range=tr,
    )
    assert "SELECT t.province AS province," in sql2
    assert sql2.endswith("GROUP BY t.province")


def test_join_sql_deterministic(join_metric_store, join_schema_store) -> None:
    tr = TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1))
    sqls = {
        build_metric_sql(
            join_metric_store.get("gmv_star"), join_metric_store,
            join_schema_store, dimensions=["ch.channel_name"], time_range=tr,
        )
        for _ in range(10)
    }
    assert len(sqls) == 1


def test_join_ratio_uses_output_names(join_metric_store, join_schema_store) -> None:
    sql = build_metric_sql(
        join_metric_store.get("aov_star"), join_metric_store, join_schema_store,
        dimensions=["ch.channel_name"],
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
    )
    # outer query must reference the bare output name, never "den.ch.channel_name"
    assert "SELECT den.channel_name," in sql
    assert "den.ch.channel_name" not in sql
    assert "ON den.channel_name = num.channel_name" in sql


def test_join_sql_passes_validator(join_metric_store, join_schema_store) -> None:
    sql = build_metric_sql(
        join_metric_store.get("gmv_star"), join_metric_store, join_schema_store,
        dimensions=["ch.channel_name", "province"],
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
    )
    result = validate_sql(sql, join_schema_store)
    assert result.ok, result.errors
    assert "dim.dim_channel" in result.tables


def test_ratio_declaring_joins_rejected(join_schema_store) -> None:
    yaml_text = """
metrics:
  - name: base
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
  - name: bad_ratio
    type: ratio
    numerator: base
    denominator: base
    joins: [{table: dim.dim_channel, alias: ch, local_key: channel}]
"""
    store, errors = MetricStore.from_text(yaml_text, join_schema_store)
    assert any("ratio 指标不能直接声明 joins" in e for e in errors)
    assert store.get("bad_ratio") is None


@pytest.fixture()
def star_sqlite_runtime(tmp_path):
    """Runtime backed by sqlite with a fact table star-joined to a dim table."""
    import sqlite3

    from seatunnel_agent.text2sql.executor import DatabaseConfig
    from seatunnel_agent.text2sql.schema import parse_ddl

    db = tmp_path / "star.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)"
    )
    conn.execute(
        "CREATE TABLE dim_channel(channel TEXT, channel_name TEXT, is_deleted INT)"
    )
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", [
        ("o1", 60.0, "app", "2026-03-01"),
        ("o2", 40.0, "app", "2026-03-01"),
        ("o3", 50.0, "web", "2026-03-01"),
        ("o4", 80.0, "app", "2026-03-02"),
        ("o5", 70.0, "web", "2026-03-02"),
    ])
    conn.executemany("INSERT INTO dim_channel VALUES (?,?,?)", [
        ("app", "手机App", 0),
        ("web", "网页端", 0),
        ("old", "已下线", 1),
    ])
    conn.commit()
    conn.close()

    ddl = _SQLITE_DDL + """
CREATE TABLE dim_channel(
  channel string COMMENT '渠道ID',
  channel_name string COMMENT '渠道名称',
  is_deleted int COMMENT '删除标记'
)
COMMENT '渠道维表';
"""
    metrics_yaml = """
metrics:
  - name: gmv
    display_name: GMV
    table: sales
    expression: SUM(amount)
    time_column: dt
    joins:
      - table: dim_channel
        alias: ch
        local_key: channel
        filters: ["is_deleted = 0"]
    dimensions: [channel, ch.channel_name]
"""
    schema_store = SchemaStore(parse_ddl(ddl))
    metric_store, errors = MetricStore.from_text(metrics_yaml, schema_store)
    assert errors == []
    return Text2SQLRuntime(
        store=schema_store,
        metrics=metric_store,
        ds_type="sqlite",
        db_config=DatabaseConfig(ds_type="sqlite", host="", port=0, database=str(db)),
    )


def test_star_join_end_to_end(star_sqlite_runtime) -> None:
    """build_metric_sql tool -> execute_sql on a real sqlite star schema."""
    rt = star_sqlite_runtime
    out = json.loads(execute_text2sql_tool("build_metric_sql", {
        "metric": "gmv",
        "dimensions": ["ch.channel_name"],
        "start_date": "2026-03-01",
        "end_date": "2026-03-02",
    }, rt))
    assert out.get("success"), out
    assert out["metric"]["joins"][0]["alias"] == "ch"

    res = json.loads(execute_text2sql_tool("execute_sql", {
        "sql": out["sql"], "user_query": "各渠道GMV",
    }, rt))
    assert res.get("success"), res
    got = {tuple(r) for r in res["preview_rows"]}
    assert got == {("手机App", 180.0), ("网页端", 120.0)}


def test_star_join_attribution(star_sqlite_runtime) -> None:
    """run_attribution drills a dim-table dimension (alias.column)."""
    rt = star_sqlite_runtime
    out = json.loads(execute_text2sql_tool("run_attribution", {
        "metric": "gmv",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
        "dimension": "ch.channel_name",
    }, rt))
    assert out.get("success"), out
    breakdown = out["dimensions"][0]
    assert breakdown["dimension"] == "ch.channel_name"
    assert breakdown["check_ok"] is True
    top = {r["value"]: r["delta"] for r in breakdown["top_contributors"]}
    assert top == {"手机App": -20.0, "网页端": 20.0}


# ----------------------------------------------------------------------
# Attribution v2: ratio two-factor split + crossed dimensions
# ----------------------------------------------------------------------


def test_ratio_factor_split_identity() -> None:
    from seatunnel_agent.text2sql.attribution import ratio_factor_split

    split = ratio_factor_split(120.0, 90.0, 400.0, 450.0)
    assert split is not None and split["check_ok"]
    assert abs(split["delta"] - (90.0 / 450.0 - 120.0 / 400.0)) < 1e-12
    assert abs(
        split["numerator_effect"] + split["denominator_effect"] - split["delta"]
    ) < 1e-12
    # numerator fell -> negative numerator effect; denominator rose -> negative
    assert split["numerator_effect"] < 0 and split["denominator_effect"] < 0

    assert ratio_factor_split(1.0, 2.0, 0.0, 10.0) is None
    assert ratio_factor_split(1.0, 2.0, 10.0, 0.0) is None


def test_attribution_cross_dimensions_pure() -> None:
    """Crossed drill keeps the contribution identity (pure execute_fn)."""
    from seatunnel_agent.text2sql.attribution import run_attribution
    from seatunnel_agent.text2sql.schema import parse_ddl

    ddl = """
CREATE TABLE sales(
  order_id string COMMENT 'id',
  amount double COMMENT 'amt',
  channel string COMMENT 'chan',
  province string COMMENT 'prov',
  dt string COMMENT 'date'
)
COMMENT 'sales';
"""
    yaml_text = """
metrics:
  - name: gmv
    display_name: GMV
    table: sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel, province]
"""
    schema_store = SchemaStore(parse_ddl(ddl))
    store, errors = MetricStore.from_text(yaml_text, schema_store)
    assert errors == []

    def execute(sql: str):
        is_curr = "2026-03-02" in sql
        if "GROUP BY channel, province" in sql:
            if is_curr:
                return (["channel", "province", "gmv"],
                        [("app", "GD", 70.0), ("app", "ZJ", 20.0), ("web", "GD", 70.0)])
            return (["channel", "province", "gmv"],
                    [("app", "GD", 90.0), ("app", "ZJ", 10.0), ("web", "GD", 50.0)])
        if "GROUP BY" in sql:
            key = "channel" if "SELECT channel" in sql else "province"
            data = {
                ("channel", False): [("app", 100.0), ("web", 50.0)],
                ("channel", True): [("app", 90.0), ("web", 70.0)],
                ("province", False): [("GD", 140.0), ("ZJ", 10.0)],
                ("province", True): [("GD", 140.0), ("ZJ", 20.0)],
            }
            return [key, "gmv"], data[(key, is_curr)]
        return ["gmv"], [(160.0 if is_curr else 150.0,)]

    result = run_attribution(
        store.get("gmv"), store, schema_store, execute,
        curr_range=TimeRange(start=date(2026, 3, 2), end=date(2026, 3, 2)),
        prev_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
        cross_dimensions=["channel", "province"],
    )
    # 2 totals + 2×2 single dims + 2 cross = 8
    assert result.sql_count == 8
    crossed = result.dimensions[-1]
    assert crossed.dimension == "channel × province"
    assert crossed.check_ok
    by_key = {r.value: r for r in crossed.rows}
    assert abs(by_key["app / GD"].delta - (-20.0)) < 1e-12
    assert abs(by_key["web / GD"].delta - 20.0) < 1e-12
    # explicit cross_dimensions promotes the crossed view to the headline
    assert result.best_dimension == "channel × province"


def test_attribution_cross_bad_pair() -> None:
    from seatunnel_agent.text2sql.attribution import run_attribution
    from seatunnel_agent.text2sql.schema import parse_ddl

    schema_store = SchemaStore(parse_ddl(_SQLITE_DDL))
    store, errors = MetricStore.from_text(_SQLITE_METRICS, schema_store)
    assert errors == []
    with pytest.raises(MetricError, match="两个不同的维度"):
        run_attribution(
            store.get("gmv"), store, schema_store, lambda sql: ([], []),
            curr_range=TimeRange(start=date(2026, 3, 2), end=date(2026, 3, 2)),
            prev_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
            cross_dimensions=["channel", "channel"],
        )


def test_tool_run_attribution_ratio_factor_split(sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool("run_attribution", {
        "metric": "aov",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
    }, sqlite_runtime))
    assert out.get("success"), out
    split = out.get("factor_split")
    assert split is not None and split["check_ok"]
    # prev: 150/3 = 50, curr: 160/3 -> delta ~ 3.3333
    assert abs(split["prev_ratio"] - 50.0) < 1e-6
    assert abs(
        split["numerator_effect"] + split["denominator_effect"] - split["delta"]
    ) < 1e-4  # rounded to 6 decimals in the payload
    assert "factor_split" in out["note"]


def test_tool_run_attribution_cross_sqlite(star_sqlite_runtime) -> None:
    out = json.loads(execute_text2sql_tool("run_attribution", {
        "metric": "gmv",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
        "cross_dimensions": ["channel", "ch.channel_name"],
    }, star_sqlite_runtime))
    assert out.get("success"), out
    labels = [b["dimension"] for b in out["dimensions"]]
    assert "channel × ch.channel_name" in labels
    crossed = out["dimensions"][-1]
    assert crossed["check_ok"] is True
    values = {r["value"] for r in crossed["top_contributors"]}
    assert "app / 手机App" in values


def test_attribution_cross_validated_before_queries() -> None:
    """Invalid cross_dimensions must fail BEFORE any SQL runs (review fix)."""
    from seatunnel_agent.text2sql.attribution import run_attribution
    from seatunnel_agent.text2sql.schema import parse_ddl

    schema_store = SchemaStore(parse_ddl(_SQLITE_DDL))
    store, errors = MetricStore.from_text(_SQLITE_METRICS, schema_store)
    assert errors == []
    calls: list[str] = []

    def execute(sql: str):
        calls.append(sql)
        return ["gmv"], [(1.0,)]

    with pytest.raises(MetricError, match="不在指标"):
        run_attribution(
            store.get("gmv"), store, schema_store, execute,
            curr_range=TimeRange(start=date(2026, 3, 2), end=date(2026, 3, 2)),
            prev_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
            cross_dimensions=["channel", "no_such_dim"],
        )
    assert calls == []  # zero queries spent on invalid input


def test_join_qualify_protects_backticks(join_schema_store) -> None:
    """Backtick-quoted identifiers must not be rewritten to `t.col` (which
    would be an invalid identifier) — review fix."""
    yaml_text = """
metrics:
  - name: gmv_bt
    table: dwd.dwd_trade_order_di
    expression: SUM(`pay_amount`)
    time_column: dt
    joins:
      - {table: dim.dim_channel, alias: ch, local_key: channel}
    dimensions: [ch.channel_name]
"""
    store, errors = MetricStore.from_text(yaml_text, join_schema_store)
    assert errors == []
    sql = build_metric_sql(
        store.get("gmv_bt"), store, join_schema_store,
        time_range=TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 1)),
    )
    assert "SUM(`pay_amount`)" in sql          # untouched inside backticks
    assert "`t.pay_amount`" not in sql
    assert "t.dt = '20260301'" in sql          # unquoted refs still qualified


def test_api_metrics_attribution_ratio_factor_split(sqlite_runtime, monkeypatch) -> None:
    """REST ratio attribution carries factor_split (parity with the tool)."""
    pytest.importorskip("fastapi")
    from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

    monkeypatch.setattr(
        SchemaStore, "from_db",
        classmethod(lambda cls, ex: cls(parse_ddl(_SQLITE_DDL))),
    )
    resp = _client().post("/api/text2sql/metrics/attribution", json={
        "metric": "aov",
        "curr_start": "2026-03-02",
        "prev_start": "2026-03-01",
        "ds_type": "sqlite",
        "db_config": {"database": sqlite_runtime.db_config.database},
        "metrics_yaml": _SQLITE_METRICS,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["type"] == "ratio"
    split = data.get("factor_split")
    assert split is not None and split["check_ok"]
    assert abs(split["prev_ratio"] - 50.0) < 1e-6
    assert abs(
        split["numerator_effect"] + split["denominator_effect"] - split["delta"]
    ) < 1e-4
