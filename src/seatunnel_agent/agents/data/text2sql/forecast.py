"""Deterministic metric forecasting (指标预测) — LLM-free.

Model: ordinary least squares linear trend + additive weekday seasonality
(offsets are the per-weekday mean of the detrended residuals, available
once the history covers at least two full weeks), plus additive CN
statutory-holiday / makeup-workday offsets (per-class residual means from
:mod:`calendar_cn`, active once the history contains at least
``HOLIDAY_MIN_DAYS`` days of that class). The prediction interval
is ``yhat ± 1.96 × σ`` where σ is the sample standard deviation of the
final residuals — a self-check of how well the model fits the history.

Same philosophy as attribution: the math is exact and reproducible; the
LLM only narrates the numbers.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from . import calendar_cn

#: minimum history points required to fit anything at all
MIN_POINTS = 7
#: weekday seasonality kicks in only with two full weeks of history
SEASONALITY_MIN_POINTS = 14
#: holiday / makeup-workday offsets need at least this many observed days
#: of that class in the history (below that the mean is just noise)
HOLIDAY_MIN_DAYS = 2

#: supported series grains; week periods start on Monday, month on the 1st
GRAINS = ("day", "week", "month")


def _next_period(d: date, grain: str) -> date:
    """The start of the period after the one starting at ``d``."""
    if grain == "week":
        return d + timedelta(days=7)
    if grain == "month":
        return date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return d + timedelta(days=1)


def _fill_gaps(
    points: list[tuple[date, float | None]], fill: str, grain: str
) -> list[tuple[date, float]]:
    """Return a contiguous period series between the first and last date.

    Keys must be period-start dates for the grain (any day for 'day',
    Mondays for 'week', 1sts for 'month'); a misaligned key would be
    silently dropped, so it raises instead. ``fill='zero'`` treats missing
    periods as 0 (additive metrics: no rows means nothing happened);
    ``fill='ffill'`` carries the last value forward (ratio metrics: 0
    would be a fake caliber).
    """
    by_day = dict(points)
    days = sorted(by_day)
    out: list[tuple[date, float]] = []
    # seed forward-fill from the first observed value so a leading missing
    # day is not filled with the fake 0 ffill exists to avoid
    prev = 0.0
    if fill == "ffill":
        prev = next((by_day[d] for d in days if by_day[d] is not None), 0.0)
    cur = days[0]
    visited: set[date] = set()
    while cur <= days[-1]:
        visited.add(cur)
        val = by_day.get(cur)
        if val is None:
            val = prev if fill == "ffill" else 0.0
        out.append((cur, float(val)))
        prev = float(val)
        cur = _next_period(cur, grain)
    stray = set(days) - visited
    if stray:
        raise ValueError(
            f"points must be {grain}-period start dates; "
            f"misaligned: {sorted(stray)[0].isoformat()}"
        )
    return out


def forecast_series(
    points: list[tuple[date, float | None]],
    horizon: int = 7,
    fill: str = "zero",
    grain: str = "day",
) -> dict[str, Any]:
    """Forecast ``horizon`` periods past the last observed period.

    ``points`` are (period_start, value) observations (unordered, gaps
    allowed, None values treated as missing; period starts: any day for
    'day' grain, Mondays for 'week', 1sts for 'month'). Weekday and CN
    holiday seasonality only apply at day grain. Returns a JSON-ready dict
    with the per-period forecasts, the fitted trend slope and the residual
    σ. Raises ``ValueError`` when the history is too short.
    """
    if grain not in GRAINS:
        raise ValueError(f"grain must be one of {GRAINS}")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    cleaned = [(d, v) for d, v in points if d is not None]
    observed = {d for d, v in cleaned if v is not None}
    if len(observed) < MIN_POINTS:
        raise ValueError(
            f"need at least {MIN_POINTS} observed history {grain}s, "
            f"got {len(observed)}"
        )
    series = _fill_gaps(cleaned, fill, grain)
    n = len(series)
    ys = [v for _, v in series]

    # OLS linear trend on the day index 0..n-1
    mean_x = (n - 1) / 2.0
    mean_y = sum(ys) / n
    sxx = sum((i - mean_x) ** 2 for i in range(n))
    sxy = sum((i - mean_x) * (ys[i] - mean_y) for i in range(n))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x

    def _trend(i: int) -> float:
        return intercept + slope * i

    # additive weekday offsets from the detrended residuals (day grain only)
    seasonal = grain == "day" and n >= SEASONALITY_MIN_POINTS
    offsets = dict.fromkeys(range(7), 0.0)
    if seasonal:
        buckets: dict[int, list[float]] = {wd: [] for wd in range(7)}
        for i, (d, v) in enumerate(series):
            buckets[d.weekday()].append(v - _trend(i))
        for wd, vals in buckets.items():
            if vals:
                offsets[wd] = sum(vals) / len(vals)

    # exogenous CN-calendar offsets (节假日/调休补班) from the residuals
    # left after trend + weekday; each class needs HOLIDAY_MIN_DAYS observed
    # days, and days in years the static calendar does not cover are never
    # flagged (calendar_cn degrades to False instead of guessing)
    def _class_offset(flag) -> float:
        vals = [
            v - _trend(i) - offsets[d.weekday()]
            for i, (d, v) in enumerate(series)
            if flag(d)
        ]
        if len(vals) < HOLIDAY_MIN_DAYS:
            return 0.0
        return sum(vals) / len(vals)

    if grain == "day":
        holiday_offset = _class_offset(calendar_cn.is_holiday)
        makeup_offset = _class_offset(calendar_cn.is_makeup_workday)
    else:  # a week/month period is not a single calendar day
        holiday_offset = makeup_offset = 0.0
    holiday_adjusted = holiday_offset != 0.0 or makeup_offset != 0.0

    def _calendar_offset(d: date) -> float:
        if calendar_cn.is_holiday(d):
            return holiday_offset
        if calendar_cn.is_makeup_workday(d):
            return makeup_offset
        return 0.0

    residuals = [
        v - _trend(i) - offsets[d.weekday()] - _calendar_offset(d)
        for i, (d, v) in enumerate(series)
    ]
    if n > 1:
        r_mean = sum(residuals) / n
        sigma = (sum((r - r_mean) ** 2 for r in residuals) / (n - 1)) ** 0.5
    else:
        sigma = 0.0

    last_day = series[-1][0]
    forecasts = []
    day = last_day
    for k in range(1, horizon + 1):
        day = _next_period(day, grain)
        yhat = _trend(n - 1 + k) + offsets[day.weekday()] + _calendar_offset(day)
        band = 1.96 * sigma
        row = {
            "day": day.isoformat(),
            "yhat": round(yhat, 4),
            "lo": round(yhat - band, 4),
            "hi": round(yhat + band, 4),
        }
        if calendar_cn.is_holiday(day):
            row["is_holiday"] = True
        forecasts.append(row)

    method = "ols_trend+weekday_seasonality" if seasonal else "ols_trend"
    if holiday_adjusted:
        method += "+cn_holiday"
    return {
        "method": method,
        "grain": grain,
        # period count; the key keeps its historical name at day grain
        ("history_days" if grain == "day" else "history_periods"): n,
        "history_start": series[0][0].isoformat(),
        "history_end": last_day.isoformat(),
        "horizon": horizon,
        ("slope_per_day" if grain == "day" else "slope_per_period"):
            round(slope, 6),
        "sigma": round(sigma, 6),
        "holiday_offset": round(holiday_offset, 6),
        "makeup_workday_offset": round(makeup_offset, 6),
        "forecasts": forecasts,
    }
