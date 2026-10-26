"""Tests for the deterministic metric forecaster (forecast.py), the daily
series SQL builder, and the forecast_metric tool (sqlite end-to-end)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.agents.data.text2sql.executor import DatabaseConfig
from seatunnel_agent.agents.data.text2sql.forecast import forecast_series
from seatunnel_agent.agents.data.text2sql.metrics import (
    MetricStore,
    build_metric_series_sql,
)
from seatunnel_agent.agents.data.text2sql.partition import TimeRange
from seatunnel_agent.agents.data.text2sql.qlog import QueryLogger
from seatunnel_agent.agents.data.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.agents.data.text2sql.tools import (
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
# CN holiday calendar + holiday offsets
# ----------------------------------------------------------------------


def test_calendar_cn_official_counts() -> None:
    from seatunnel_agent.agents.data.text2sql import calendar_cn as cal

    by_year = {y: sum(1 for d in cal.HOLIDAYS if d.year == y)
               for y in (2024, 2025, 2026)}
    # per the State Council notices: 2024=1+8+3+5+1+3+7, 2025=1+8+3+5+3+8,
    # 2026=3+9+3+5+3+3+7
    assert by_year == {2024: 28, 2025: 28, 2026: 33}
    makeup = {y: sum(1 for d in cal.MAKEUP_WORKDAYS if d.year == y)
              for y in (2024, 2025, 2026)}
    assert makeup == {2024: 8, 2025: 5, 2026: 6}
    # makeup workdays are weekends by definition, never also holidays
    assert all(d.weekday() >= 5 for d in cal.MAKEUP_WORKDAYS)
    assert not (cal.HOLIDAYS & cal.MAKEUP_WORKDAYS)
    assert not cal.covers(date(2027, 1, 1))
    assert not cal.is_holiday(date(2027, 2, 8))  # uncovered year degrades


def test_forecast_holiday_offset_applied() -> None:
    # flat level 100 with a -40 dip on the 2026 Mid-Autumn days (9/25-27);
    # the forecast window covers National Day (10/1-7), which must inherit
    # the holiday offset and carry the is_holiday flag
    from seatunnel_agent.agents.data.text2sql import calendar_cn as cal

    start = date(2026, 9, 3)
    pts = [
        (start + timedelta(days=i),
         60.0 if cal.is_holiday(start + timedelta(days=i)) else 100.0)
        for i in range(28)  # ends 2026-09-30
    ]
    out = forecast_series(pts, horizon=8)  # 10/1 .. 10/8
    assert out["method"].endswith("+cn_holiday")
    assert out["holiday_offset"] < -10
    by_day = {f["day"]: f for f in out["forecasts"]}
    # a holiday forecast sits clearly below the non-holiday day after it
    assert by_day["2026-10-01"]["yhat"] < by_day["2026-10-08"]["yhat"] - 10
    assert by_day["2026-10-01"].get("is_holiday") is True
    assert "is_holiday" not in by_day["2026-10-08"]


def test_forecast_no_holidays_in_window_is_unchanged() -> None:
    # March 2026 has no statutory holidays: offsets stay 0, method unchanged
    out = forecast_series(_linear(28), horizon=3)
    assert out["holiday_offset"] == 0.0
    assert out["makeup_workday_offset"] == 0.0
    assert out["method"] == "ols_trend+weekday_seasonality"
    assert all("is_holiday" not in f for f in out["forecasts"])


def test_forecast_single_holiday_day_not_enough() -> None:
    # only one holiday day in history (< HOLIDAY_MIN_DAYS): no adjustment
    start = date(2025, 12, 19)  # 28 days -> ends 2026-01-15, 元旦 1/1-3
    pts = [(start + timedelta(days=i), 100.0) for i in range(14)]
    # window 12/19 .. 1/1 contains exactly one holiday day (2026-01-01)
    out = forecast_series(pts, horizon=2)
    assert out["holiday_offset"] == 0.0
    assert not out["method"].endswith("+cn_holiday")


# ----------------------------------------------------------------------
# week / month grain
# ----------------------------------------------------------------------


def test_forecast_week_grain_linear_trend() -> None:
    start = date(2026, 3, 2)  # a Monday
    pts = [(start + timedelta(weeks=i), 1000.0 + 70.0 * i) for i in range(10)]
    out = forecast_series(pts, horizon=2, grain="week")
    assert out["grain"] == "week"
    assert out["method"] == "ols_trend"  # no weekday seasonality at week grain
    assert out["slope_per_period"] == pytest.approx(70.0, abs=1e-6)
    assert "slope_per_day" not in out
    assert out["history_periods"] == 10
    # next periods step by 7 days from the last Monday (2026-05-04)
    assert [f["day"] for f in out["forecasts"]] == ["2026-05-11", "2026-05-18"]
    assert [f["yhat"] for f in out["forecasts"]] == pytest.approx(
        [1700.0, 1770.0])


def test_forecast_month_grain_steps_by_month() -> None:
    pts = [(date(2025, m, 1), 100.0 * m) for m in range(1, 11)]
    out = forecast_series(pts, horizon=3, grain="month")
    assert [f["day"] for f in out["forecasts"]] == [
        "2025-11-01", "2025-12-01", "2026-01-01"]
    assert out["forecasts"][0]["yhat"] == pytest.approx(1100.0, abs=1e-6)


def test_forecast_misaligned_period_rejected() -> None:
    pts = [(date(2026, 3, 2) + timedelta(weeks=i), 100.0) for i in range(8)]
    pts.append((date(2026, 3, 4), 100.0))  # a Wednesday among Mondays
    with pytest.raises(ValueError, match="misaligned"):
        forecast_series(pts, horizon=1, grain="week")
    with pytest.raises(ValueError, match="grain"):
        forecast_series(pts[:8], horizon=1, grain="quarter")


def test_forecast_tool_week_grain(runtime) -> None:
    # fixture loads 2026-03-01..03-28; full ISO weeks are 3/2-8, 3/9-15,
    # 3/16-22 — the partial edge weeks (3/1 alone, 3/23-28) must be dropped,
    # which leaves too few points -> clear error, no silent bad fit
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "horizon_days": 2, "grain": "week",
        "history_days": 56, "end_date": "2026-03-28",
    }, runtime))
    assert not out.get("success")
    assert "历史数据不足" in out["error"]


def test_forecast_tool_week_grain_end_to_end(tmp_path, stores) -> None:
    schema_store, metric_store = stores
    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sales("
        "order_id TEXT, amount REAL, refund REAL, channel TEXT, dt TEXT)")
    start = date(2026, 1, 5)  # a Monday; 12 full weeks -> ends 2026-03-29
    rows = []
    for i in range(12 * 7):
        d = (start + timedelta(days=i)).isoformat()
        rows.append((f"o{i}", 100.0, 10.0, "app", d))
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
        "metric": "gmv", "horizon_days": 2, "grain": "week",
        "history_days": 84, "end_date": "2026-03-29",
    }, rt))
    assert out.get("success"), out
    assert out["grain"] == "week"
    assert out["history_periods"] == 12
    # flat 700/week -> flat forecast, Mondays after the last full week
    assert out["forecasts"][0]["day"] == "2026-03-30"
    assert out["forecasts"][0]["yhat"] == pytest.approx(700.0, abs=1e-6)


def test_forecast_tool_ratio_refuses_week_grain(runtime) -> None:
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "refund_rate", "grain": "week", "end_date": "2026-03-28",
    }, runtime))
    assert not out.get("success")
    assert "比率指标" in out["error"]


def test_forecast_tool_bad_grain(runtime) -> None:
    out = json.loads(execute_text2sql_tool("forecast_metric", {
        "metric": "gmv", "grain": "quarter",
    }, runtime))
    assert out["error"].startswith("grain must be")


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
