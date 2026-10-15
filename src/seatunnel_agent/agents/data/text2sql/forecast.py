"""Deterministic metric forecasting (指标预测) — LLM-free.

Model: ordinary least squares linear trend + additive weekday seasonality
(offsets are the per-weekday mean of the detrended residuals, available
once the history covers at least two full weeks). The prediction interval
is ``yhat ± 1.96 × σ`` where σ is the sample standard deviation of the
final residuals — a self-check of how well the model fits the history.

Same philosophy as attribution: the math is exact and reproducible; the
LLM only narrates the numbers.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

#: minimum history points required to fit anything at all
MIN_POINTS = 7
#: weekday seasonality kicks in only with two full weeks of history
SEASONALITY_MIN_POINTS = 14


def _fill_gaps(
    points: list[tuple[date, float | None]], fill: str
) -> list[tuple[date, float]]:
    """Return a contiguous daily series between the first and last date.

    ``fill='zero'`` treats missing days as 0 (additive metrics: no rows
    means nothing happened); ``fill='ffill'`` carries the last value
    forward (ratio metrics: 0 would be a fake caliber).
    """
    by_day = {d: v for d, v in points}
    days = sorted(by_day)
    out: list[tuple[date, float]] = []
    # seed forward-fill from the first observed value so a leading missing
    # day is not filled with the fake 0 ffill exists to avoid
    prev = 0.0
    if fill == "ffill":
        prev = next((by_day[d] for d in days if by_day[d] is not None), 0.0)
    cur = days[0]
    while cur <= days[-1]:
        val = by_day.get(cur)
        if val is None:
            val = prev if fill == "ffill" else 0.0
        out.append((cur, float(val)))
        prev = float(val)
        cur += timedelta(days=1)
    return out


def forecast_series(
    points: list[tuple[date, float | None]],
    horizon: int = 7,
    fill: str = "zero",
) -> dict[str, Any]:
    """Forecast ``horizon`` days past the last observed date.

    ``points`` are (day, value) observations (unordered, gaps allowed,
    None values treated as missing). Returns a JSON-ready dict with the
    per-day forecasts, the fitted trend slope and the residual σ.
    Raises ``ValueError`` when the history is too short.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    cleaned = [(d, v) for d, v in points if d is not None]
    observed = {d for d, v in cleaned if v is not None}
    if len(observed) < MIN_POINTS:
        raise ValueError(
            f"need at least {MIN_POINTS} observed history days, "
            f"got {len(observed)}"
        )
    series = _fill_gaps(cleaned, fill)
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

    # additive weekday offsets from the detrended residuals
    seasonal = n >= SEASONALITY_MIN_POINTS
    offsets = {wd: 0.0 for wd in range(7)}
    if seasonal:
        buckets: dict[int, list[float]] = {wd: [] for wd in range(7)}
        for i, (d, v) in enumerate(series):
            buckets[d.weekday()].append(v - _trend(i))
        for wd, vals in buckets.items():
            if vals:
                offsets[wd] = sum(vals) / len(vals)

    residuals = [
        v - _trend(i) - offsets[d.weekday()]
        for i, (d, v) in enumerate(series)
    ]
    if n > 1:
        r_mean = sum(residuals) / n
        sigma = (sum((r - r_mean) ** 2 for r in residuals) / (n - 1)) ** 0.5
    else:
        sigma = 0.0

    last_day = series[-1][0]
    forecasts = []
    for k in range(1, horizon + 1):
        day = last_day + timedelta(days=k)
        yhat = _trend(n - 1 + k) + offsets[day.weekday()]
        band = 1.96 * sigma
        forecasts.append({
            "day": day.isoformat(),
            "yhat": round(yhat, 4),
            "lo": round(yhat - band, 4),
            "hi": round(yhat + band, 4),
        })

    return {
        "method": "ols_trend+weekday_seasonality" if seasonal else "ols_trend",
        "history_days": n,
        "history_start": series[0][0].isoformat(),
        "history_end": last_day.isoformat(),
        "horizon": horizon,
        "slope_per_day": round(slope, 6),
        "sigma": round(sigma, 6),
        "forecasts": forecasts,
    }
