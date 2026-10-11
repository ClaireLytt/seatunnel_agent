"""Tests for the deterministic metric forecaster (forecast.py), the daily
series SQL builder, and the forecast_metric tool (sqlite end-to-end)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.text2sql.executor import DatabaseConfig
from seatunnel_agent.text2sql.forecast import forecast_series
from seatunnel_agent.text2sql.metrics import (
    MetricStore,
    build_metric_series_sql,
)
from seatunnel_agent.text2sql.partition import TimeRange
from seatunnel_agent.text2sql.qlog import QueryLogger
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.text2sql.tools import (
    TOOL_DEFINITIONS,
    Text2SQLRuntime,
    execute_text2sql_tool,
)

_DDL = """
CREATE TABLE sales(
  order_id string COMMENT '订单ID',
  amount double COMMENT '金额',
  refund double COMMENT '退款额',
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
  - name: refund_amount
    display_name: 退款额
    description: 退款合计
    table: sales
    expression: SUM(refund)
    time_column: dt
    dimensions: [channel]
  - name: refund_rate
    display_name: 退款率
    description: 退款额 / GMV
    type: ratio
    numerator: refund_amount
    denominator: gmv
"""


@pytest.fixture()
def stores() -> tuple[SchemaStore, MetricStore]:
    schema_store = SchemaStore(parse_ddl(_DDL))
    metric_store, errors = MetricStore.from_text(_METRICS, schema_store)
    assert not errors, errors
    return schema_store, metric_store


# ----------------------------------------------------------------------
# forecast_series (pure math)
# ----------------------------------------------------------------------


def _linear(n: int, start=date(2026, 3, 1), a=100.0, b=5.0):
    return [(start + timedelta(days=i), a + b * i) for i in range(n)]


def test_forecast_recovers_linear_trend() -> None:
    out = forecast_series(_linear(28), horizon=3)
    assert out["slope_per_day"] == pytest.approx(5.0, abs=1e-6)
    assert out["sigma"] == pytest.approx(0.0, abs=1e-6)
    # next days continue the line exactly: y(28)=100+5*28=240 ...
    assert [f["yhat"] for f in out["forecasts"]] == pytest.approx(
        [240.0, 245.0, 250.0])
    # zero residuals -> degenerate interval equals the point forecast
    assert out["forecasts"][0]["lo"] == out["forecasts"][0]["hi"]
    assert out["forecasts"][0]["day"] == "2026-03-29"
    assert out["method"] == "ols_trend+weekday_seasonality"


def test_forecast_recovers_weekday_seasonality() -> None:
    # flat level 100 with a +30 bump every Saturday
    start = date(2026, 3, 2)  # a Monday
    pts = [
        (start + timedelta(days=i),
         100.0 + (30.0 if (start + timedelta(days=i)).weekday() == 5 else 0.0))
        for i in range(28)
    ]
    out = forecast_series(pts, horizon=7)
    by_day = {f["day"]: f["yhat"] for f in out["forecasts"]}
    sat = next(d for d in by_day
               if date.fromisoformat(d).weekday() == 5)
    mon = next(d for d in by_day
               if date.fromisoformat(d).weekday() == 0)
    assert by_day[sat] - by_day[mon] == pytest.approx(30.0, abs=1.0)


def test_forecast_gap_fill_modes() -> None:
    pts = _linear(14)
    del pts[5]  # a missing day
    zero = forecast_series(pts, horizon=1, fill="zero")
    ffill = forecast_series(pts, horizon=1, fill="ffill")
    assert zero["history_days"] == ffill["history_days"] == 14
    # true line continues at y(14) = 100 + 5*14 = 170; forward-fill stays
    # near it, a zero-filled gap distorts the fit measurably more
    assert ffill["forecasts"][0]["yhat"] == pytest.approx(170.0, abs=3.0)
    assert abs(zero["forecasts"][0]["yhat"] - 170.0) > abs(
        ffill["forecasts"][0]["yhat"] - 170.0)


def test_forecast_short_history_and_bad_horizon() -> None:
    with pytest.raises(ValueError, match="at least"):
        forecast_series(_linear(5), horizon=3)
    with pytest.raises(ValueError, match="horizon"):
        forecast_series(_linear(14), horizon=0)


def test_forecast_none_values_treated_as_missing() -> None:
    pts: list = _linear(14)
    pts[3] = (pts[3][0], None)
    out = forecast_series(pts, horizon=1, fill="ffill")
    assert out["history_days"] == 14


def test_forecast_ffill_leading_none_uses_first_observed() -> None:
    # a leading undefined ratio day must not be filled with a fake 0
    pts: list = [(date(2026, 3, 1) + timedelta(days=i), 0.5)
                 for i in range(14)]
    pts[0] = (pts[0][0], None)
    out = forecast_series(pts, horizon=1, fill="ffill")
    assert out["slope_per_day"] == pytest.approx(0.0, abs=1e-9)
    assert out["forecasts"][0]["yhat"] == pytest.approx(0.5, abs=1e-6)


def test_forecast_mostly_none_history_rejected() -> None:
    # 7 distinct days but only 1 observed value -> insufficient history
    pts: list = [(date(2026, 3, 1) + timedelta(days=i), None)
                 for i in range(7)]
    pts[0] = (pts[0][0], 100.0)
    with pytest.raises(ValueError, match="observed"):
        forecast_series(pts, horizon=1)


# ----------------------------------------------------------------------
# build_metric_series_sql
# ----------------------------------------------------------------------


def test_series_sql_additive(stores) -> None:
    schema_store, metric_store = stores
    sql = build_metric_series_sql(
        metric_store.get("gmv"), metric_store, schema_store,
        TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 28)),
    )
    assert "GROUP BY dt" in sql
    assert sql.rstrip().endswith("ORDER BY dt")
    assert "SUM(amount) AS gmv" in sql
    # pure function: byte-identical on repeat
    assert sql == build_metric_series_sql(
        metric_store.get("gmv"), metric_store, schema_store,
        TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 28)),
    )


def test_series_sql_ratio_joins_on_day(stores) -> None:
    schema_store, metric_store = stores
    sql = build_metric_series_sql(
        metric_store.get("refund_rate"), metric_store, schema_store,
        TimeRange(start=date(2026, 3, 1), end=date(2026, 3, 28)),
    )
    assert "num.dt = den.dt" in sql
    # LEFT JOIN miss (den rows, no num rows) must read as rate 0, not NULL
    assert "COALESCE(num.refund_amount, 0) * 1.0" in sql
    assert "NULLIF(den.gmv, 0)" in sql
    assert sql.rstrip().endswith("ORDER BY den.dt")


# ----------------------------------------------------------------------
# forecast_metric tool (sqlite end-to-end)
# ----------------------------------------------------------------------


def test_forecast_tool_registered() -> None:
    assert any(t["name"] == "forecast_metric" for t in TOOL_DEFINITIONS)


@pytest.fixture()
def runtime(tmp_path, stores) -> Text2SQLRuntime:
    schema_store, metric_store = stores
    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales("
        "order_id TEXT, amount REAL, refund REAL, channel TEXT, dt TEXT)")
    start = date(2026, 3, 1)
    rows = []
    for i in range(28):
        d = (start + timedelta(days=i)).isoformat()
        rows.append((f"o{i}a", 100.0 + 5.0 * i, 10.0, "app", d))
        rows.append((f"o{i}b", 50.0, 5.0, "web", d))
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return Text2SQLRuntime(
        store=schema_store, metrics=metric_store, ds_type="sqlite",
        db_config=DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)),
        logger=QueryLogger(log_dir=tmp_path),
    )


def test_forecast_tool_end_to_end(runtime) -> None:
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "horizon_days": 3, "history_days": 28,
        "end_date": "2026-03-28",
    }, runtime))
    assert out.get("success"), out
    assert out["slope_per_day"] == pytest.approx(5.0, abs=1e-6)
    assert len(out["forecasts"]) == 3
    # daily total = (100+5i) + 50; day 28 -> 100+5*28+50 = 290
    assert out["forecasts"][0]["yhat"] == pytest.approx(290.0, abs=1e-6)
    assert out["history_tail"][-1]["day"] == "2026-03-28"
    assert "ORDER BY dt" in out["sql"]


def test_forecast_tool_ratio_metric(runtime) -> None:
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "refund_rate", "horizon_days": 2, "history_days": 28,
        "end_date": "2026-03-28",
    }, runtime))
    assert out.get("success"), out
    assert len(out["forecasts"]) == 2
    # refund rate declines as gmv grows: forecast stays in (0, 0.1]
    assert 0.0 < out["forecasts"][0]["yhat"] <= 0.1


def test_forecast_tool_refuses_truncated_series(runtime) -> None:
    runtime.default_limit = 10  # below history_days -> oldest rows kept
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "history_days": 28, "end_date": "2026-03-28",
    }, runtime))
    assert "截断" in out["error"]


def test_forecast_tool_sums_subday_rows(tmp_path, stores) -> None:
    """A timestamp-grain time_column yields several rows per day: the
    additive partial sums must be summed, not last-write-wins."""
    schema_store, metric_store = stores
    db = tmp_path / "ts.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales("
        "order_id TEXT, amount REAL, refund REAL, channel TEXT, dt TEXT)")
    start = date(2026, 3, 1)
    rows = []
    for i in range(14):
        d = (start + timedelta(days=i)).isoformat()
        # two intra-day rows: 10:00 and 18:00, daily total = 100
        rows.append((f"o{i}a", 60.0, 0.0, "app", f"{d} 10:00:00"))
        rows.append((f"o{i}b", 40.0, 0.0, "web", f"{d} 18:00:00"))
    conn.executemany("INSERT INTO sales VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    rt = Text2SQLRuntime(
        store=schema_store, metrics=metric_store, ds_type="sqlite",
        db_config=DatabaseConfig(
            ds_type="sqlite", host="", port=0, database=str(db)),
        logger=QueryLogger(log_dir=tmp_path),
    )
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "horizon_days": 1, "history_days": 14,
        "end_date": "2026-03-14",
    }, rt))
    assert out.get("success"), out
    # flat 100/day -> forecast stays at 100, not an arbitrary partial sum
    assert out["forecasts"][0]["yhat"] == pytest.approx(100.0, abs=1e-6)
    # ratio metrics cannot be re-aggregated across sub-day rows
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "refund_rate", "horizon_days": 1, "history_days": 14,
        "end_date": "2026-03-14",
    }, rt))
    assert "粒度细于天" in out["error"]


def test_forecast_tool_errors(runtime) -> None:
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "nope"}, runtime))
    assert "not defined" in out["error"]
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "end_date": "2030-01-01"}, runtime))
    assert "历史数据不足" in out["error"]
