"""Tests for M4: cron parsing, the subscription store, subscription runs
(sqlite end-to-end), Feishu payloads, the scheduler, and the MCP server."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.agents.data.text2sql.metrics import MetricError, MetricStore
from seatunnel_agent.agents.data.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.agents.data.text2sql.subscriptions import (
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


def test_store_refuses_to_overwrite_corrupt_file(tmp_path) -> None:
    path = tmp_path / "subs.json"
    corrupt = '{"broken": [truncated'
    path.write_text(corrupt, encoding="utf-8")
    store = SubscriptionStore(path)
    with pytest.raises(ValueError, match="subs.json"):
        store.add(name="x", cron="0 9 * * *", source_type="metric", metric="m")
    # the corrupt file must not have been overwritten
    assert path.read_text(encoding="utf-8") == corrupt
    # read-only access stays lenient
    assert store.list() == []


_INTERLEAVE_WORKER = """
import sys
from seatunnel_agent.agents.data.text2sql.subscriptions import SubscriptionStore
store = SubscriptionStore(sys.argv[1])
for i in range(int(sys.argv[3])):
    store.add(name=f"sub-{sys.argv[2]}-{i}", cron="0 9 * * *",
              source_type="metric", metric="m")
"""


def test_store_interleaved_cross_process_writes_lose_nothing(tmp_path) -> None:
    """Two real processes hammering add() concurrently: without a
    cross-process lock the read-modify-write races drop entries."""
    import subprocess
    import sys

    path = str(tmp_path / "subs.json")
    n = 25
    procs = [
        subprocess.Popen([sys.executable, "-c", _INTERLEAVE_WORKER,
                          path, tag, str(n)])
        for tag in ("a", "b")
    ]
    for p in procs:
        assert p.wait(timeout=120) == 0
    names = {e["name"] for e in SubscriptionStore(path).list()}
    assert len(names) == 2 * n, f"lost {2 * n - len(names)} entries"


def test_store_write_lock_timeout_raises(tmp_path) -> None:
    from seatunnel_agent.common.filelock import FileLockTimeout, file_lock

    path = tmp_path / "subs.json"
    store = SubscriptionStore(path, lock_timeout=0.3)
    with file_lock(path):  # simulate another process holding the lock
        with pytest.raises(FileLockTimeout, match="file lock"):
            store.add(name="x", cron="0 9 * * *",
                      source_type="metric", metric="m")
    # lock released -> write succeeds again
    entry = store.add(name="x", cron="0 9 * * *",
                      source_type="metric", metric="m")
    assert store.get(entry["id"]) is not None


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
    from seatunnel_agent.agents.data.text2sql.favorites import FavoritesStore

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
# metric_watch (anomaly alert subscription)
# ----------------------------------------------------------------------


def _watch_sub(sales_db: str, **over) -> dict:
    sub = {
        "id": "w1", "name": "GMV异动监控", "cron": "0 9 * * *",
        "source_type": "metric_watch", "metric": "gmv",
        "dimensions": ["channel"], "threshold_pct": 5.0, "watch_mode": "dod",
        "ds_type": "sqlite", "connection": "", "database": sales_db,
        "webhook_url": "https://example/hook", "enabled": True,
    }
    sub.update(over)
    return sub


def test_metric_watch_alerts_over_threshold(sales_db, stores) -> None:
    """昨天(03-02)=160 vs 前天(03-01)=150 → +6.67%, 阈值 5% → 告警."""
    schema_store, metric_store = stores
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    outcome = run_subscription(
        _watch_sub(sales_db), schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert outcome["status"] == "alerted", outcome
    assert outcome["change_rate_pct"] == pytest.approx(6.67, abs=0.01)
    assert pushes and pushes[0][2] is False  # alert card is red
    title, body, _ = pushes[0]
    assert "GMV异动监控" in title
    assert "+6.67%" in body
    # top contributors on channel present
    assert "主要贡献" in body
    assert outcome["top_contributors"]


def test_metric_watch_silent_below_threshold(sales_db, stores) -> None:
    schema_store, metric_store = stores
    pushes: list = []
    outcome = run_subscription(
        _watch_sub(sales_db, threshold_pct=50.0), schema_store, metric_store,
        today=date(2026, 3, 3),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "no_change"
    assert pushes == []  # silence by design


def _series_db(tmp_path, days: list[tuple[str, float]]) -> str:
    db = tmp_path / "series.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    conn.executemany(
        "INSERT INTO sales VALUES (?,?,?,?)",
        [(f"o{i}", amt, "app", dt) for i, (dt, amt) in enumerate(days)],
    )
    conn.commit()
    conn.close()
    return str(db)


def test_metric_watch_model_alerts_outside_band(tmp_path, stores) -> None:
    """平稳 100/天的两周历史,昨天 500 → 落在 95% 区间外 → 告警."""
    schema_store, metric_store = stores
    days = [(f"2026-03-{d:02d}", 100.0) for d in range(1, 15)]
    days.append(("2026-03-15", 500.0))
    db = _series_db(tmp_path, days)
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    outcome = run_subscription(
        _watch_sub(db, watch_mode="model"), schema_store, metric_store,
        today=date(2026, 3, 16), push_fn=fake_push,
    )
    assert outcome["status"] == "alerted", outcome
    assert outcome["curr"] == pytest.approx(500.0)
    assert outcome["baseline"]["hi"] < 500.0
    title, body, _ = pushes[0]
    assert "模型基线" in body and "预期" in body


def test_metric_watch_model_silent_inside_band(tmp_path, stores) -> None:
    schema_store, metric_store = stores
    days = [(f"2026-03-{d:02d}", 100.0) for d in range(1, 15)]
    days.append(("2026-03-15", 100.0))  # exactly the flat baseline
    db = _series_db(tmp_path, days)
    pushes: list = []
    outcome = run_subscription(
        _watch_sub(db, watch_mode="model"), schema_store, metric_store,
        today=date(2026, 3, 16),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "no_change", outcome
    assert outcome["baseline"]["lo"] <= 100.0 <= outcome["baseline"]["hi"]
    assert pushes == []


def test_metric_watch_model_insufficient_history(tmp_path, stores) -> None:
    schema_store, metric_store = stores
    db = _series_db(tmp_path, [("2026-03-14", 100.0), ("2026-03-15", 90.0)])
    outcome = run_subscription(
        _watch_sub(db, watch_mode="model"), schema_store, metric_store,
        today=date(2026, 3, 16), push_fn=lambda *a, **k: (True, "ok"),
    )
    assert outcome["status"] == "no_data", outcome
    assert "历史不足" in outcome["note"]


def test_metric_watch_model_missing_day_with_lagging_table(tmp_path, stores) -> None:
    """表最新数据停在 03-13,昨日(03-15)无行 → 断更提示,不发 -100% 假告警."""
    schema_store, metric_store = stores
    days = [(f"2026-03-{d:02d}", 100.0) for d in range(1, 14)]
    db = _series_db(tmp_path, days)
    pushes: list = []
    outcome = run_subscription(
        _watch_sub(db, watch_mode="model"), schema_store, metric_store,
        today=date(2026, 3, 16),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "no_data", outcome
    assert "数据未更新至昨日" in outcome["note"]
    assert pushes == []


def test_metric_watch_alert_card_has_attribution(tmp_path, stores) -> None:
    """告警卡片带贡献率(来自归因引擎,而非裸 delta)."""
    schema_store, metric_store = stores
    # 两个渠道:app 平稳,web 昨日暴涨 → web 应为主要贡献
    db = tmp_path / "attr.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    rows = []
    for d in range(1, 15):
        rows.append((f"a{d}", 100.0, "app", f"2026-03-{d:02d}"))
        rows.append((f"w{d}", 50.0, "web", f"2026-03-{d:02d}"))
    rows.append(("a15", 100.0, "app", "2026-03-15"))
    rows.append(("w15", 500.0, "web", "2026-03-15"))
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body))
        return True, "ok"

    outcome = run_subscription(
        _watch_sub(str(db), watch_mode="model"), schema_store, metric_store,
        today=date(2026, 3, 16), push_fn=fake_push,
    )
    assert outcome["status"] == "alerted", outcome
    top = outcome["top_contributors"]
    assert top[0]["value"] == "web"
    assert top[0]["contribution_pct"] is not None
    _, body = pushes[0]
    assert "贡献" in body and "web" in body


def test_freshness_alerts_when_stale(tmp_path, stores) -> None:
    schema_store, metric_store = stores
    db = _series_db(tmp_path, [("2026-03-10", 100.0)])
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    sub = _watch_sub(db, source_type="freshness", max_lag_days=1)
    outcome = run_subscription(
        sub, schema_store, metric_store,
        today=date(2026, 3, 16), push_fn=fake_push,
    )
    assert outcome["status"] == "alerted", outcome
    assert outcome["max_by_table"]["sales"] == "2026-03-10"
    title, body, ok = pushes[0]
    assert ok is False and "断更" in body and "2026-03-10" in body


def test_freshness_silent_when_fresh(tmp_path, stores) -> None:
    schema_store, metric_store = stores
    db = _series_db(tmp_path, [("2026-03-15", 100.0)])
    pushes: list = []
    outcome = run_subscription(
        _watch_sub(db, source_type="freshness", max_lag_days=1),
        schema_store, metric_store, today=date(2026, 3, 16),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "fresh", outcome
    assert pushes == []


def test_freshness_store_validation(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    with pytest.raises(ValueError, match="指标名"):
        store.add(name="f", cron="0 9 * * *", source_type="freshness")
    with pytest.raises(ValueError, match="max_lag_days"):
        store.add(name="f", cron="0 9 * * *", source_type="freshness",
                  metric="gmv", max_lag_days=0)
    entry = store.add(name="f", cron="0 9 * * *", source_type="freshness",
                      metric="gmv", max_lag_days=2)
    assert entry["max_lag_days"] == 2


def test_backtest_model_vs_threshold(tmp_path, stores) -> None:
    """工作日 100 / 周末 50 的 6 周序列 + 一个真尖峰:
    dod 阈值 20% 每个周末边界都误报,model 基线学会星期形态只报尖峰."""
    from seatunnel_agent.agents.data.text2sql.executor import (
        DatabaseConfig,
        create_executor,
    )
    from seatunnel_agent.agents.data.text2sql.subscriptions import backtest_watch

    schema_store, metric_store = stores
    start = date(2026, 3, 2)  # Monday
    days = []
    for i in range(42):
        d = start + timedelta(days=i)
        amt = 50.0 if d.weekday() >= 5 else 100.0
        days.append((d.isoformat(), amt))
    spike_day = start + timedelta(days=38)  # a weekday
    days = [(ds, 1000.0 if ds == spike_day.isoformat() else v) for ds, v in days]
    db = _series_db(tmp_path, days)
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=db))
    end = start + timedelta(days=41)

    model = backtest_watch(
        _watch_sub(db, watch_mode="model"), schema_store, metric_store,
        executor, end=end, days=14,
    )
    assert model["alert_count"] == 1, model["alerts"]
    assert model["alerts"][0]["day"] == spike_day.isoformat()

    dod = backtest_watch(
        _watch_sub(db, watch_mode="dod", threshold_pct=20.0),
        schema_store, metric_store, executor, end=end, days=14,
    )
    # every weekday<->weekend boundary trips the fixed threshold
    assert dod["alert_count"] > 3
    assert any(a["day"] == spike_day.isoformat() for a in dod["alerts"])


def test_backtest_unknown_metric(tmp_path, stores) -> None:
    from seatunnel_agent.agents.data.text2sql.executor import (
        DatabaseConfig,
        create_executor,
    )
    from seatunnel_agent.agents.data.text2sql.subscriptions import backtest_watch

    schema_store, metric_store = stores
    db = _series_db(tmp_path, [("2026-03-01", 1.0)])
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=db))
    with pytest.raises(MetricError):
        backtest_watch(
            _watch_sub(db, metric="nope"), schema_store, metric_store,
            executor, end=date(2026, 3, 15),
        )


def test_metric_watch_dod_missing_day_lagging_table(tmp_path, stores) -> None:
    """dod 模式同样受断更保护:表停在 03-13,昨日无行 → no_data 而非 -100%."""
    schema_store, metric_store = stores
    db = _series_db(tmp_path, [(f"2026-03-{d:02d}", 100.0) for d in range(1, 14)])
    pushes: list = []
    outcome = run_subscription(
        _watch_sub(db, watch_mode="dod"), schema_store, metric_store,
        today=date(2026, 3, 16),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "no_data", outcome
    assert "数据未更新至昨日" in outcome["note"]
    assert pushes == []


_DIGEST_METRICS = """
metrics:
  - name: gmv
    display_name: GMV
    table: sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel]
    unit: 元
    targets: {month: 10000}
  - name: order_cnt
    display_name: 单量
    table: sales
    expression: COUNT(order_id)
    time_column: dt
"""


def test_digest_card(tmp_path) -> None:
    """日报卡:每指标一行 值/环比/月目标达成;未定义指标单行标注不炸卡."""
    schema_store = SchemaStore(parse_ddl(_DDL))
    metric_store, errors = MetricStore.from_text(_DIGEST_METRICS, schema_store)
    assert errors == []
    days = [("2026-03-14", 100.0), ("2026-03-15", 110.0)]
    db = _series_db(tmp_path, days)
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    sub = _watch_sub(
        db, source_type="digest", metrics=["gmv", "order_cnt", "nope"],
    )
    outcome = run_subscription(
        sub, schema_store, metric_store,
        today=date(2026, 3, 16), push_fn=fake_push,
    )
    assert outcome["status"] == "success", outcome
    title, body, ok = pushes[0]
    assert ok is True and "经营日报" in body
    # GMV: 昨日 110,前日 100 → 环比 +10%;MTD=210 / 10000 → 2.1%
    assert "GMV: 110.00 元（环比 +10.0%） · 月目标达成 2.1%" in body
    assert "单量: 1.00" in body
    assert "- nope: 未定义" in body
    by_metric = {r["metric"]: r for r in outcome["rows"]}
    assert by_metric["gmv"]["dod_pct"] == pytest.approx(10.0)
    assert by_metric["gmv"]["month_completion_pct"] == pytest.approx(2.1)


def test_watch_repeat_alert_suppressed_and_recovers(sales_db, stores) -> None:
    """持续异常只推首日;同向重复被抑制;恢复日推一张绿卡."""
    schema_store, metric_store = stores
    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    # day 1: 03-02=160 vs 03-01=150 → +6.67% 超 5% 阈值 → 告警 + 置状态
    out1 = run_subscription(
        _watch_sub(sales_db), schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert out1["status"] == "alerted"
    assert out1["alert_state"] == {
        "active": True, "direction": "up", "since": "2026-03-02",
    }
    assert len(pushes) == 1

    # day 2(同样的数据形态,带着 day1 的状态)→ 同向重复 → 抑制,不推卡
    sub2 = _watch_sub(sales_db, alert_state=out1["alert_state"])
    out2 = run_subscription(
        sub2, schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert out2["status"] == "suppressed"
    assert out2["alert_state"]["since"] == "2026-03-02"  # 保留首日
    assert len(pushes) == 1  # 没有新卡

    # 恢复日:阈值调高到不触发,带着 active 状态 → 推绿卡,状态清空
    sub3 = _watch_sub(
        sales_db, threshold_pct=50.0, alert_state=out1["alert_state"],
    )
    out3 = run_subscription(
        sub3, schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert out3["status"] == "recovered"
    assert out3["alert_state"] == {}
    title, body, ok = pushes[-1]
    assert ok is True and "已恢复" in body and "2026-03-02" in body


def test_watch_direction_change_alerts_again(sales_db, stores) -> None:
    """方向反转(up→down)视为新事件,不被抑制."""
    schema_store, metric_store = stores
    pushes: list = []
    sub = _watch_sub(
        sales_db,
        alert_state={"active": True, "direction": "down", "since": "2026-02-28"},
    )
    out = run_subscription(
        sub, schema_store, metric_store, today=date(2026, 3, 3),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert out["status"] == "alerted"  # 当前是 up,与 down 状态不同向
    assert out["alert_state"]["direction"] == "up"
    assert len(pushes) == 1


def test_store_record_alert_state(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    entry = store.add(name="w", cron="0 9 * * *", source_type="metric_watch",
                      metric="gmv")
    store.record_alert_state(
        entry["id"], {"active": True, "direction": "up", "since": "2026-03-02"},
    )
    reread = store.get(entry["id"])
    assert reread["alert_state"]["direction"] == "up"


def test_digest_store_validation(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    with pytest.raises(ValueError, match="最多"):
        store.add(name="d", cron="0 9 * * *", source_type="digest",
                  metrics=[f"m{i}" for i in range(11)])
    entry = store.add(name="d", cron="0 9 * * *", source_type="digest",
                      metrics=["gmv", " order_cnt "])
    assert entry["metrics"] == ["gmv", "order_cnt"]


def test_metric_watch_store_validation(tmp_path) -> None:
    store = SubscriptionStore(tmp_path / "subs.json")
    with pytest.raises(ValueError, match="指标名"):
        store.add(name="x", cron="0 9 * * *", source_type="metric_watch")
    with pytest.raises(ValueError, match="watch_mode"):
        store.add(name="x", cron="0 9 * * *", source_type="metric_watch",
                  metric="gmv", watch_mode="weird")
    with pytest.raises(ValueError, match="threshold"):
        store.add(name="x", cron="0 9 * * *", source_type="metric_watch",
                  metric="gmv", threshold_pct=0)
    entry = store.add(name="x", cron="0 9 * * *", source_type="metric_watch",
                      metric="gmv", threshold_pct=8, watch_mode="wow")
    assert entry["threshold_pct"] == 8.0 and entry["watch_mode"] == "wow"


def test_push_feishu_with_img_key(monkeypatch) -> None:
    captured: dict = {}

    class _Resp:
        def read(self):
            return b'{"code": 0}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, _ = push_feishu("https://hook/x", "t", "b", img_key="img_v3_xyz")
    assert ok
    elements = captured["body"]["card"]["elements"]
    assert elements[-1] == {
        "tag": "img", "img_key": "img_v3_xyz",
        "alt": {"tag": "plain_text", "content": "chart"},
    }


def test_upload_feishu_image_needs_creds(monkeypatch) -> None:
    from seatunnel_agent.agents.data.text2sql.subscriptions import upload_feishu_image

    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    assert upload_feishu_image(b"png") == ""  # no creds -> graceful ''


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


def test_scheduler_catches_up_minutes_missed_by_slow_run(tmp_path) -> None:
    """A slow run_fn can push the next tick past a whole minute; the cron
    fire due in that skipped minute must be made up on the next check."""
    store = SubscriptionStore(tmp_path / "subs.json")
    slow = store.add(name="slow", cron="30 9 * * *", source_type="metric",
                     metric="gmv")
    missed = store.add(name="missed", cron="31 9 * * *", source_type="metric",
                       metric="gmv")

    runs: list[str] = []

    def fake_run(sub):
        runs.append(sub["id"])
        return {"status": "success", "error": ""}

    sched = Scheduler(store=store, run_fn=fake_run)
    assert sched.check_once(datetime(2026, 3, 2, 9, 30, 10)) == [slow["id"]]
    # the slow run stalled the loop: the next tick lands at 9:32, having
    # never observed any 9:31 timestamp
    fired = sched.check_once(datetime(2026, 3, 2, 9, 32, 10))
    assert missed["id"] in fired, "9:31 cron silently dropped"
    # the catch-up must not double-fire anything
    assert runs.count(missed["id"]) == 1
    assert runs.count(slow["id"]) == 1
    assert sched.check_once(datetime(2026, 3, 2, 9, 32, 30)) == []


def test_scheduler_catchup_window_param(tmp_path) -> None:
    """catchup_minutes=2 replays only the 2 most recent missed minutes."""
    store = SubscriptionStore(tmp_path / "subs.json")
    store.add(name="every", cron="* * * * *", source_type="metric", metric="gmv")

    runs: list[str] = []

    def fake_run(sub):
        runs.append(sub["id"])
        return {"status": "success", "error": ""}

    sched = Scheduler(store=store, run_fn=fake_run, catchup_minutes=2)
    sched.check_once(datetime(2026, 3, 2, 9, 0, 10))
    runs.clear()
    # stall: next tick is 6 minutes later → 5 missed minutes + current;
    # only 2 missed + current may fire
    sched.check_once(datetime(2026, 3, 2, 9, 6, 10))
    assert len(runs) == 3


def test_scheduler_catchup_window_env(tmp_path, monkeypatch) -> None:
    """SEATUNNEL_SUB_CATCHUP_MINUTES overrides the default; bad/out-of-range
    values are clamped or fall back to the default."""
    store = SubscriptionStore(tmp_path / "subs.json")
    monkeypatch.setenv("SEATUNNEL_SUB_CATCHUP_MINUTES", "1")
    sched = Scheduler(store=store, run_fn=lambda s: {"status": "success"})
    assert sched.catchup_minutes == 1
    # explicit constructor arg wins over env
    assert Scheduler(store=store, catchup_minutes=5).catchup_minutes == 5
    # clamping: below 0 → 0, above 1440 → 1440
    monkeypatch.setenv("SEATUNNEL_SUB_CATCHUP_MINUTES", "-3")
    assert Scheduler(store=store).catchup_minutes == 0
    monkeypatch.setenv("SEATUNNEL_SUB_CATCHUP_MINUTES", "99999")
    assert Scheduler(store=store).catchup_minutes == 1440
    # non-numeric → default 10
    monkeypatch.setenv("SEATUNNEL_SUB_CATCHUP_MINUTES", "oops")
    assert Scheduler(store=store).catchup_minutes == 10
    monkeypatch.delenv("SEATUNNEL_SUB_CATCHUP_MINUTES")
    assert Scheduler(store=store).catchup_minutes == 10


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
    from seatunnel_agent.agents.data.text2sql.mcp_server import build_tool_functions

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
    from seatunnel_agent.agents.data.text2sql.mcp_server import build_tool_functions

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
    from seatunnel_agent.agents.data.text2sql.mcp_server import build_tool_functions

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


def test_metric_watch_ratio_metric(tmp_path) -> None:
    """v2 unlock: metric_watch works on ratio metrics (e.g. refund rate)."""
    schema_store = SchemaStore(parse_ddl(
        "CREATE TABLE sales(amount double, refund double, dt string, "
        "channel string) COMMENT 's';"
    ))
    metric_store, errors = MetricStore.from_text(
        """
metrics:
  - name: gmv
    display_name: GMV
    table: sales
    expression: SUM(amount)
    time_column: dt
    dimensions: [channel]
  - name: refund_amount
    display_name: Refunds
    table: sales
    expression: SUM(refund)
    time_column: dt
    dimensions: [channel]
  - name: refund_rate
    display_name: Refund rate
    type: ratio
    numerator: refund_amount
    denominator: gmv
""",
        schema_store,
    )
    assert not errors, errors

    db = tmp_path / "ratio.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales(amount REAL, refund REAL, dt TEXT, channel TEXT)")
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?)", [
        (100.0, 10.0, "2026-03-01", "app"),
        (50.0, 5.0, "2026-03-01", "web"),   # 03-01 rate = 15/150 = 0.10
        (100.0, 25.0, "2026-03-02", "app"),
        (60.0, 7.0, "2026-03-02", "web"),   # 03-02 rate = 32/160 = 0.20
    ])
    conn.commit()
    conn.close()

    pushes: list[tuple] = []

    def fake_push(url, title, body, ok=True, **kw):
        pushes.append((title, body, ok))
        return True, "ok"

    sub = {
        "id": "w2", "name": "退款率异动", "cron": "0 9 * * *",
        "source_type": "metric_watch", "metric": "refund_rate",
        "dimensions": [], "threshold_pct": 50.0, "watch_mode": "dod",
        "ds_type": "sqlite", "connection": "", "database": str(db),
        "webhook_url": "https://example/hook", "enabled": True,
    }
    outcome = run_subscription(
        sub, schema_store, metric_store,
        today=date(2026, 3, 3), push_fn=fake_push,
    )
    assert outcome["status"] == "alerted", outcome
    assert outcome["curr"] == pytest.approx(0.20)
    assert outcome["prev"] == pytest.approx(0.10)
    assert outcome["change_rate_pct"] == pytest.approx(100.0)
    # per-dim deltas are labeled as changes, not additive contributions
    assert pushes and "各维度变化" in pushes[0][1]


def test_metric_watch_ratio_null_is_no_data(tmp_path) -> None:
    """A NULL ratio (denominator 0 / no rows) is undefined, not a -100% drop."""
    schema_store = SchemaStore(parse_ddl(
        "CREATE TABLE sales(amount double, refund double, dt string) "
        "COMMENT 's';"
    ))
    metric_store, errors = MetricStore.from_text(
        """
metrics:
  - name: gmv
    display_name: GMV
    table: sales
    expression: SUM(amount)
    time_column: dt
  - name: refund_amount
    display_name: Refunds
    table: sales
    expression: SUM(refund)
    time_column: dt
  - name: refund_rate
    display_name: Refund rate
    type: ratio
    numerator: refund_amount
    denominator: gmv
""",
        schema_store,
    )
    assert not errors, errors
    db = tmp_path / "null_ratio.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(amount REAL, refund REAL, dt TEXT)")
    # 03-01 has data; 03-02 (yesterday) has none -> ratio undefined
    conn.execute("INSERT INTO sales VALUES (100.0, 10.0, '2026-03-01')")
    conn.commit()
    conn.close()

    pushes: list = []
    outcome = run_subscription(
        {
            "id": "w3", "name": "退款率异动", "cron": "0 9 * * *",
            "source_type": "metric_watch", "metric": "refund_rate",
            "dimensions": [], "threshold_pct": 10.0, "watch_mode": "dod",
            "ds_type": "sqlite", "connection": "", "database": str(db),
            "webhook_url": "https://example/hook", "enabled": True,
        },
        schema_store, metric_store,
        today=date(2026, 3, 3),
        push_fn=lambda *a, **k: (pushes.append(a), (True, "ok"))[1],
    )
    assert outcome["status"] == "no_data", outcome
    assert outcome["curr"] is None
    assert pushes == []  # no false alert card
