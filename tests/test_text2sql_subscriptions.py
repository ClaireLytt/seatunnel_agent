"""Tests for M4: cron parsing, the subscription store, subscription runs
(sqlite end-to-end), Feishu payloads, the scheduler, and the MCP server."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.text2sql.metrics import MetricStore
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.text2sql.subscriptions import (
    Scheduler,
    SubscriptionStore,
    builtin_params,
    parse_cron,
    push_feishu,
    render_card_markdown,
    run_subscription,
)

_DDL = """
CREATE TABLE sales(
  order_id string COMMENT '订单ID',
  amount double COMMENT '金额',
  channel string COMMENT '渠道',
  dt string COMMENT '日期'
) COMMENT '销售明细';
"""

_METRICS = """
metrics:
  - name: gmv
    display_name: GMV
    aliases: [成交总额]
    description: 金额合计
    table: sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel]
"""


# ----------------------------------------------------------------------
# Cron
# ----------------------------------------------------------------------


def test_cron_basic_match() -> None:
    spec = parse_cron("30 9 * * *")
    assert spec.matches(datetime(2026, 3, 2, 9, 30))
    assert not spec.matches(datetime(2026, 3, 2, 9, 31))
    assert not spec.matches(datetime(2026, 3, 2, 10, 30))


def test_cron_step_range_list() -> None:
    spec = parse_cron("*/15 8-10 1,15 * 0-4")
    dt = datetime(2026, 6, 1, 8, 45)  # Monday(0), day 1
    assert spec.matches(dt)
    assert not spec.matches(dt.replace(minute=50))
    assert not spec.matches(dt.replace(day=2))
    # Saturday June 6 2026 -> weekday 5, excluded by 0-4
    assert not spec.matches(datetime(2026, 6, 6, 8, 45))


def test_cron_invalid() -> None:
    for bad in ("* * * *", "61 * * * *", "a * * * *", "*/0 * * * *", "5-1 * * * *"):
        with pytest.raises(ValueError):
            parse_cron(bad)


def test_builtin_params() -> None:
    p = builtin_params(date(2026, 3, 2))
    assert p["yesterday"] == "2026-03-01"
    assert p["yesterday_pt"] == "20260301"
    assert p["month_start"] == "2026-03-01"
    assert p["today_pt"] == "20260302"


# ----------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------


def test_store_crud(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    entry = store.add(
        name="日报", cron="0 9 * * *", source_type="metric",
        metric="gmv", dimensions=["channel"], ds_type="sqlite",
        database="x.db", webhook_url="https://example/hook",
    )
    assert store.get(entry["id"])["name"] == "日报"
    assert store.set_enabled(entry["id"], False)
    assert store.get(entry["id"])["enabled"] is False
    store.record_run(entry["id"], "success")
    got = store.get(entry["id"])
    assert got["last_status"] == "success" and got["last_run_at"]
    assert store.delete(entry["id"])
    assert store.list() == []


def test_store_validation(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    with pytest.raises(ValueError, match="cron"):
        store.add(name="x", cron="not cron", source_type="metric", metric="m")
    with pytest.raises(ValueError, match="指标名"):
        store.add(name="x", cron="0 9 * * *", source_type="metric")
    with pytest.raises(ValueError, match="source_type"):
        store.add(name="x", cron="0 9 * * *", source_type="weird")


def test_store_env_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("T2S_SUBSCRIPTIONS_PATH", str(tmp_path / "env.json"))
    store = SubscriptionStore()
    assert store.path == tmp_path / "env.json"


# ----------------------------------------------------------------------
# run_subscription (sqlite end-to-end)
# ----------------------------------------------------------------------


@pytest.fixture()
def sales_db(tmp_path) -> str:
    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", [
        ("o1", 100.0, "app", "2026-03-01"),
        ("o2", 50.0, "web", "2026-03-01"),
        ("o3", 80.0, "app", "2026-03-02"),
        ("o4", 80.0, "web", "2026-03-02"),
    ])
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture()
def stores() -> tuple[SchemaStore, MetricStore]:
    schema_store = SchemaStore(parse_ddl(_DDL))
    metric_store, errors = MetricStore.from_text(_METRICS, schema_store)
    assert errors == []
    return schema_store, metric_store


def _metric_sub(sales_db: str, **over) -> dict:
    sub = {
        "id": "s1", "name": "GMV日报", "cron": "0 9 * * *",
        "source_type": "metric", "metric": "gmv",
        "dimensions": ["channel"], "lookback_days": 1,
        "ds_type": "sqlite", "connection": "", "database": sales_db,
        "webhook_url": "https://example/hook", "enabled": True,
    }
    sub.update(over)
    return sub


def test_run_metric_subscription(sales_db, stores) -> None:
    schema_store, metric_store = stores
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((url, title, body, ok))
        return True, "ok"

    outcome = run_subscription(
        _metric_sub(sales_db), schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert outcome["status"] == "success", outcome
    # lookback 1 with today=03-03 -> [03-02, 03-02]
    assert "dt = '2026-03-02'" in outcome["sql"]
    assert outcome["row_count"] == 2
    assert len(pushes) == 1
    url, title, body, ok = pushes[0]
    assert ok is True and "GMV日报" in title
    assert "channel" in body and "app" in body


def test_run_favorite_subscription(sales_db, stores, tmp_path) -> None:
    from seatunnel_agent.text2sql.favorites import FavoritesStore

    schema_store, metric_store = stores
    favs = FavoritesStore(tmp_path / "favs.json")
    fav = favs.save(
        "昨日单量", "SELECT COUNT(order_id) AS cnt FROM sales WHERE dt = '${yesterday}'",
    )
    sub = _metric_sub(
        sales_db, source_type="favorite", favorite_id=fav["id"], metric="",
    )
    pushes = []
    outcome = run_subscription(
        sub, schema_store, metric_store, today=date(2026, 3, 3),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
        favorites=favs,
    )
    assert outcome["status"] == "success", outcome
    assert "dt = '2026-03-02'" in outcome["sql"]
    assert outcome["rows"][0][0] == 2


def test_run_subscription_error_pushes_red_card(sales_db, stores) -> None:
    schema_store, metric_store = stores
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, ok))
        return True, "ok"

    outcome = run_subscription(
        _metric_sub(sales_db, metric="no_such_metric"),
        schema_store, metric_store, today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert outcome["status"] == "error"
    assert "未定义" in outcome["error"]
    assert pushes and pushes[0][1] is False  # red card


def test_run_subscription_never_raises(stores) -> None:
    schema_store, metric_store = stores
    outcome = run_subscription(
        _metric_sub("Z:/no/such.db"), schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=lambda *a, **k: (True, "ok"),
    )
    assert outcome["status"] == "error"


# ----------------------------------------------------------------------
# Feishu payload & card rendering
# ----------------------------------------------------------------------


def test_render_card_markdown_truncates() -> None:
    columns = ["a", "b"]
    rows = [(i, i * 2) for i in range(15)]
    body = render_card_markdown(columns, rows, max_rows=10)
    assert body.count("\n") == 11  # header + 10 rows + truncation note
    assert "共 15 行" in body


def test_push_feishu_payload(monkeypatch) -> None:
    captured: dict = {}

    class _Resp:
        def read(self):
            return b'{"code": 0}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = push_feishu("https://open.feishu.cn/hook/x", "标题", "内容", ok=False)
    assert ok is True and msg == "ok"
    card = captured["body"]["card"]
    assert card["header"]["title"]["content"] == "标题"
    assert card["header"]["template"] == "red"
    assert captured["body"]["msg_type"] == "interactive"


def test_push_feishu_error_code(monkeypatch) -> None:
    class _Resp:
        def read(self):
            return b'{"code": 19001, "msg": "invalid token"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _Resp())
    ok, msg = push_feishu("https://open.feishu.cn/hook/x", "t", "b")
    assert ok is False and "invalid token" in msg


# ----------------------------------------------------------------------
# Scheduler
# ----------------------------------------------------------------------


def test_scheduler_fires_once_per_minute(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    entry = store.add(name="x", cron="30 9 * * *", source_type="metric", metric="gmv")
    store.add(name="off", cron="30 9 * * *", source_type="metric", metric="gmv")
    off_id = store.list()[1]["id"]
    store.set_enabled(off_id, False)

    runs: list[str] = []

    def fake_run(sub):
        runs.append(sub["id"])
        return {"status": "success", "error": ""}

    sched = Scheduler(store=store, run_fn=fake_run)
    at = datetime(2026, 3, 2, 9, 30, 5)
    assert sched.check_once(at) == [entry["id"]]
    assert sched.check_once(at.replace(second=45)) == []  # same minute dedupe
    assert sched.check_once(datetime(2026, 3, 2, 9, 31)) == []  # cron mismatch
    assert sched.check_once(datetime(2026, 3, 3, 9, 30)) == [entry["id"]]
    assert runs == [entry["id"], entry["id"]]
    assert store.get(entry["id"])["last_status"] == "success"
    assert off_id not in runs


def test_scheduler_survives_bad_cron(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    entry = store.add(name="x", cron="0 9 * * *", source_type="metric", metric="gmv")
    # corrupt the cron after creation
    data = json.loads(store.path.read_text(encoding="utf-8"))
    data[0]["cron"] = "garbage"
    store.path.write_text(json.dumps(data), encoding="utf-8")
    sched = Scheduler(store=store, run_fn=lambda s: {"status": "success"})
    assert sched.check_once(datetime(2026, 3, 2, 9, 0)) == []
    assert entry  # no exception


# ----------------------------------------------------------------------
# MCP server tools
# ----------------------------------------------------------------------


@pytest.fixture()
def mcp_files(tmp_path, sales_db) -> dict:
    ddl = tmp_path / "schema.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    metrics = tmp_path / "metrics.yaml"
    metrics.write_text(_METRICS, encoding="utf-8")
    return {"ddl": str(ddl), "metrics": str(metrics), "db": sales_db}


def test_mcp_tools_default_set(mcp_files) -> None:
    from seatunnel_agent.text2sql.mcp_server import build_tool_functions

    tools = build_tool_functions(
        ddl_path=mcp_files["ddl"], metrics_path=mcp_files["metrics"],
    )
    assert "execute_readonly_sql" not in tools  # off by default

    out = json.loads(tools["list_tables"]())
    assert out["count"] == 1 and out["tables"][0]["table"] == "sales"

    out = json.loads(tools["get_table_schema"]("sales"))
    assert any(c["name"] == "amount" for c in out["columns"])
    assert "error" in json.loads(tools["get_table_schema"]("nope"))

    out = json.loads(tools["match_tables"]("销售金额"))
    assert out["candidates"][0]["table"] == "sales"

    out = json.loads(tools["match_metrics"]("昨天的成交总额"))
    assert out["candidates"][0]["name"] == "gmv"

    out = json.loads(tools["explain_metric"]("gmv"))
    assert out["expression"] == "SUM(amount)"

    out = json.loads(tools["metric_sql"](
        "gmv", dimensions="channel", start_date="2026-03-02",
    ))
    assert "SUM(amount) AS gmv" in out["sql"]
    assert "GROUP BY channel" in out["sql"]

    out = json.loads(tools["metric_sql"]("gmv", dimensions="order_id",
                                         start_date="2026-03-02"))
    assert "允许维度" in out["error"]


def test_mcp_execute_readonly(mcp_files) -> None:
    from seatunnel_agent.text2sql.mcp_server import build_tool_functions

    tools = build_tool_functions(
        ddl_path=mcp_files["ddl"], metrics_path=mcp_files["metrics"],
        ds_type="sqlite", allow_execute=True, database=mcp_files["db"],
    )
    execute = tools["execute_readonly_sql"]

    out = json.loads(execute("SELECT channel, SUM(amount) AS s FROM sales "
                             "WHERE dt = '2026-03-02' GROUP BY channel"))
    assert out["row_count"] == 2
    assert "LIMIT" in out["sql"]

    out = json.loads(execute("DELETE FROM sales"))
    assert "rejected" in out["error"]

    out = json.loads(execute("SELECT * FROM other_table"))
    assert "rejected" in out["error"]


def test_mcp_rejects_bad_config(tmp_path) -> None:
    from seatunnel_agent.text2sql.mcp_server import build_tool_functions

    with pytest.raises(RuntimeError, match="不存在"):
        build_tool_functions(ddl_path=str(tmp_path / "nope.sql"))

    ddl = tmp_path / "schema.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    bad_metrics = tmp_path / "bad.yaml"
    bad_metrics.write_text(
        "metrics:\n  - name: m\n    table: nope\n    expression: SUM(x)\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="指标定义无效"):
        build_tool_functions(ddl_path=str(ddl), metrics_path=str(bad_metrics))


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_t2s_sub_lifecycle(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("T2S_SUBSCRIPTIONS_PATH", str(tmp_path / "subs.json"))
    runner = CliRunner()

    r = runner.invoke(cli, [
        "t2s-sub", "add", "--name", "GMV日报", "--cron", "0 9 * * *",
        "--metric", "gmv", "--ds-type", "sqlite", "--database", "x.db",
    ])
    assert r.exit_code == 0, r.output
    assert "已创建订阅" in r.output

    r = runner.invoke(cli, ["t2s-sub", "list"])
    assert r.exit_code == 0 and "GMV日报" in r.output

    sub_id = SubscriptionStore(tmp_path / "subs.json").list()[0]["id"]
    r = runner.invoke(cli, ["t2s-sub", "enable", sub_id, "--off"])
    assert r.exit_code == 0

    r = runner.invoke(cli, ["t2s-sub", "rm", sub_id])
    assert r.exit_code == 0

    r = runner.invoke(cli, [
        "t2s-sub", "add", "--name", "x", "--cron", "0 9 * * *",
        "--metric", "m", "--favorite", "f",
    ])
    assert r.exit_code != 0  # metric XOR favorite


def test_cli_t2s_cron_once(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("T2S_SUBSCRIPTIONS_PATH", str(tmp_path / "subs.json"))
    r = CliRunner().invoke(cli, ["t2s-cron", "--once"])
    assert r.exit_code == 0, r.output
    assert "0 个订阅" in r.output
