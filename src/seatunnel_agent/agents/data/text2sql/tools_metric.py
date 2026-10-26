"""Metric-family tool handlers for the Text2SQL agent: matching, caliber
expansion, forecasting, attribution and provenance tracing."""

from __future__ import annotations

from typing import Any

from .executor import QueryResult
from .metrics import (
    MetricError,
    build_metric_series_sql,
    build_metric_sql,
    parse_date,
    parse_time_range,
    ratio_sides,
)
from .runtime import Text2SQLRuntime, _sanitize_db_error
from .validator import enforce_limit, validate_sql


def _metric_payload(m: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": m.name,
        "display_name": m.display_name,
        "description": m.description,
        "type": m.metric_type,
        "unit": m.unit,
        "owner": m.owner,
    }
    if m.is_ratio:
        payload["numerator"] = m.numerator
        payload["denominator"] = m.denominator
    else:
        payload["table"] = m.table
        payload["expression"] = m.expression
        payload["time_column"] = m.time_column
        payload["dimensions"] = list(m.dimensions)
        payload["default_filters"] = list(m.default_filters)
        if m.joins:
            payload["joins"] = [
                {"table": j.table, "alias": j.alias, "type": j.join_type,
                 "on": f"t.{j.local_key} = {j.alias}.{j.remote_key}"}
                for j in m.joins
            ]
    return payload


def _tool_match_metrics(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.metrics is None or len(rt.metrics) == 0:
        return {
            "candidates": [],
            "count": 0,
            "note": (
                "No metric definitions loaded (metrics.yaml). Fall back to "
                "match_tables and write the aggregation yourself."
            ),
        }
    query = inp.get("query", "")
    try:
        matches = rt.retriever.rank_metrics(query, top_n=5)
    except Exception:  # retrieval must never break the tool — degrade
        matches = rt.metrics.match(query, top_n=5)
    return {
        "candidates": [
            {**_metric_payload(r.metric), "score": round(r.score, 2), "hits": r.hits}
            for r in matches
        ],
        "count": len(matches),
    }


def _resolve_metric(
    inp: dict[str, Any], rt: Text2SQLRuntime
) -> tuple[Any, dict[str, Any] | None]:
    """Shared head of every metric-taking tool handler: the metric store
    must be loaded and the requested name defined. Returns (metric, None)
    on success, (None, error_payload) otherwise."""
    if rt.metrics is None or len(rt.metrics) == 0:
        return None, {"error": "No metric definitions loaded (metrics.yaml)"}
    name = str(inp.get("metric", "")).strip()
    metric = rt.metrics.get(name)
    if metric is None:
        known = ", ".join(m.name for m in rt.metrics.metrics)
        return None, {
            "error": f"Metric '{name}' is not defined. Known metrics: {known}"
        }
    return metric, None


def _tool_build_metric_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    metric, err = _resolve_metric(inp, rt)
    if err is not None:
        return err

    try:
        time_range = parse_time_range(
            str(inp.get("start_date", "") or ""),
            str(inp.get("end_date", "") or ""),
        )
        sql = build_metric_sql(
            metric,
            rt.metrics,
            rt.store,
            dimensions=inp.get("dimensions") or [],
            time_range=time_range,
            max_partition=str(inp.get("max_partition", "") or "").strip() or None,
            extra_filters=inp.get("extra_filters") or [],
        )
    except MetricError as exc:
        return {"error": str(exc)}
    return {
        "success": True,
        "metric": _metric_payload(metric),
        "sql": sql,
        "note": "Run this SQL with execute_sql. Do not edit the aggregation.",
    }


def _tool_forecast_metric(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    from datetime import date, timedelta

    from .forecast import forecast_series
    from .partition import TimeRange

    metric, err = _resolve_metric(inp, rt)
    if err is not None:
        return err
    name = metric.name

    grain = str(inp.get("grain") or "day").strip().lower()
    # (min, max, default) history window in DAYS per grain; the month cap
    # stays under default_limit=1000 daily rows so the truncation guard
    # below never fires on a legitimate request
    _history_bounds = {
        "day": (14, 180, 28),
        "week": (56, 364, 112),
        "month": (210, 900, 365),
    }
    if grain not in _history_bounds:
        return {"error": "grain must be one of: day, week, month"}
    lo, hi, default = _history_bounds[grain]
    try:
        horizon = max(1, min(int(inp.get("horizon_days") or 7), 30))
        history = max(lo, min(int(inp.get("history_days") or default), hi))
    except (TypeError, ValueError):
        return {"error": "horizon_days / history_days must be integers"}

    try:
        end_raw = str(inp.get("end_date", "") or "").strip()
        end = parse_date(end_raw) if end_raw else date.today() - timedelta(days=1)
        start = end - timedelta(days=history - 1)
        sql = build_metric_series_sql(
            metric, rt.metrics, rt.store, TimeRange(start=start, end=end),
        )
    except MetricError as exc:
        return {"error": str(exc)}

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return {"error": "SQL rejected: " + "; ".join(validation.errors), "sql": sql}
    final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)
    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        return {"error": _sanitize_db_error(str(exc)), "sql": sql}
    if result.truncated or result.row_count >= rt.default_limit:
        # the ascending ORDER BY + LIMIT would silently keep the OLDEST
        # rows and forecast from stale history — refuse instead
        return {
            "error": (
                f"日序列达到 {rt.default_limit} 行上限，最近的历史会被截断。"
                "请减小 history_days，或确认 time_column 是日粒度。"
            ),
            "sql": sql,
        }

    def _day(raw: Any) -> Any:
        s = str(raw).strip()
        try:
            return parse_date(s)
        except MetricError:
            return parse_date(s[:10])  # 'YYYY-MM-DD HH:MM:SS' timestamps

    try:
        # aggregate to day grain: a sub-day time_column yields several rows
        # per day — partial sums of an additive metric are summed; partial
        # ratios cannot be recombined, so refuse
        daily: dict[Any, float | None] = {}
        for r in result.rows:
            if r[0] is None:
                continue
            d = _day(r[0])
            v = None if r[-1] is None else float(r[-1])
            if d in daily:
                if metric.is_ratio:
                    return {
                        "error": (
                            "time_column 粒度细于天，比率指标无法按日重新聚合，"
                            "请为比率的分子/分母使用日粒度时间列"
                        ),
                        "sql": sql,
                    }
                if v is not None:
                    daily[d] = (daily[d] or 0.0) + v
            else:
                daily[d] = v
        points = sorted(daily.items())
    except (MetricError, TypeError, ValueError) as exc:
        return {"error": f"cannot parse the daily series: {exc}", "sql": sql}

    if grain != "day":
        if metric.is_ratio:
            # weekly/monthly ratios cannot be recombined from daily ratios
            # (same reason sub-day ratio rows are refused above)
            return {
                "error": (
                    "比率指标无法从日序列重新聚合为周/月粒度,"
                    "请用 grain=day,或分别预测分子/分母"
                ),
                "sql": sql,
            }
        from datetime import timedelta as _td

        def _period_start(d: date) -> date:
            if grain == "week":
                return d - _td(days=d.weekday())  # ISO week, Monday
            return d.replace(day=1)

        from .forecast import _next_period

        buckets: dict[date, float] = {}
        for d, v in points:
            buckets[_period_start(d)] = (
                buckets.get(_period_start(d), 0.0) + (v or 0.0)
            )
        # drop partial edge periods: a half-covered week/month would read
        # as a fake dip and bend the trend
        points = sorted(
            (p, total) for p, total in buckets.items()
            if p >= start and _next_period(p, grain) - _td(days=1) <= end
        )

    try:
        fc = forecast_series(
            points, horizon=horizon,
            fill="ffill" if metric.is_ratio else "zero",
            grain=grain,
        )
    except ValueError as exc:
        return {
            "error": f"历史数据不足，无法预测: {exc}",
            "hint": "增大 history_days 或确认该时间范围内有数据",
            "sql": sql,
        }

    rt.logger.log(
        user_query=str(inp.get("user_query", "")),
        generated_sql=final_sql, status="success",
        matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": rt.source, "metric": name, "kind": "forecast"},
    )
    return {
        "success": True,
        "metric": name,
        "display_name": metric.display_name,
        "unit": metric.unit,
        "sql": sql,
        "history_tail": [
            {"day": d.isoformat(), "value": v} for d, v in points[-14:]
        ],
        **fc,
    }


def _period_bounds(period: str, anchor: Any) -> tuple[Any, Any]:
    """(start, end) calendar bounds of the period containing *anchor* (a date)."""
    from datetime import timedelta

    if period == "month":
        start = anchor.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
    elif period == "quarter":
        start = anchor.replace(month=((anchor.month - 1) // 3) * 3 + 1, day=1)
        nxt = (start + timedelta(days=93)).replace(day=1)
    else:  # year
        start = anchor.replace(month=1, day=1)
        nxt = start.replace(year=start.year + 1)
    return start, nxt - timedelta(days=1)


def _tool_metric_target_progress(
    inp: dict[str, Any], rt: Text2SQLRuntime,
) -> dict[str, Any]:
    """Target attainment: period-to-date actual vs the metric's declared
    target, plus a deterministic projection of the period total (forecast
    when the history supports it, linear pace otherwise)."""
    from datetime import date, timedelta

    from .forecast import MIN_POINTS, forecast_series
    from .partition import TimeRange

    metric, err = _resolve_metric(inp, rt)
    if err is not None:
        return err
    period = str(inp.get("period") or "month").strip().lower()
    target = metric.targets.get(period)
    if target is None:
        declared = ", ".join(sorted(metric.targets)) or "无"
        return {
            "error": (
                f"指标 '{metric.name}' 未声明 {period} 目标"
                f"(metrics.yaml targets,已声明: {declared})"
            ),
        }
    try:
        end_raw = str(inp.get("end_date", "") or "").strip()
        end = parse_date(end_raw) if end_raw else date.today() - timedelta(days=1)
    except MetricError as exc:
        return {"error": str(exc)}
    p_start, p_end = _period_bounds(period, end)

    def _run(sql: str) -> QueryResult:
        validation = validate_sql(sql, rt.store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        return rt.executor.run(
            enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type),
            max_rows=rt.default_limit,
        )

    try:
        total_sql = build_metric_sql(
            metric, rt.metrics, rt.store,
            time_range=TimeRange(start=p_start, end=end),
        )
        result = _run(total_sql)
    except MetricError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": _sanitize_db_error(str(exc))}
    actual = (
        float(result.rows[0][-1])
        if result.rows and result.rows[0][-1] is not None else 0.0
    )

    elapsed = (end - p_start).days + 1
    total_days = (p_end - p_start).days + 1
    remaining = (p_end - end).days
    projected = actual
    method = "actual"
    if remaining > 0:
        # forecast the remaining days from the trailing 28-day series;
        # fall back to linear pace when the history is too short
        try:
            h_start = end - timedelta(days=27)
            series_sql = build_metric_series_sql(
                metric, rt.metrics, rt.store,
                TimeRange(start=h_start, end=end),
            )
            s_result = _run(series_sql)
            points = sorted(
                (parse_date(str(r[0]).strip()[:10]),
                 None if r[-1] is None else float(r[-1]))
                for r in s_result.rows if r[0] is not None
            )
            if len([1 for _, v in points if v is not None]) >= MIN_POINTS:
                fc = forecast_series(points, horizon=remaining, fill="zero")
                projected = actual + sum(row["yhat"] for row in fc["forecasts"])
                method = fc["method"]
            else:
                raise ValueError("history too short")
        except (MetricError, ValueError, TypeError):
            projected = actual / elapsed * total_days if elapsed else actual
            method = "linear_pace"
        except Exception as exc:
            return {"error": _sanitize_db_error(str(exc))}

    rt.logger.log(
        user_query=str(inp.get("user_query", "")),
        generated_sql=total_sql, status="success",
        matched_tables=[metric.table] if metric.table else [],
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": rt.source, "metric": metric.name, "kind": "target"},
    )
    return {
        "success": True,
        "metric": metric.name,
        "display_name": metric.display_name,
        "unit": metric.unit,
        "period": period,
        "period_start": p_start.isoformat(),
        "period_end": p_end.isoformat(),
        "as_of": end.isoformat(),
        "days_elapsed": elapsed,
        "days_total": total_days,
        "target": target,
        "actual": round(actual, 4),
        "completion_pct": round(actual / target * 100, 2),
        "projected_total": round(projected, 4),
        "projected_completion_pct": round(projected / target * 100, 2),
        "projection_method": method,
        "sql": total_sql,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r; None when either side has zero variance."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (sxx * syy) ** 0.5


_CORR_MIN_PAIRS = 7
_CORR_MAX_LAG = 7


def _tool_correlate_metrics(
    inp: dict[str, Any], rt: Text2SQLRuntime,
) -> dict[str, Any]:
    """Deterministic correlation between two metrics' daily series: Pearson
    r at lag 0 plus the strongest lead/lag within ±7 days. 2 SQL queries;
    the LLM narrates, never computes."""
    from datetime import date, timedelta

    from .partition import TimeRange

    if rt.metrics is None or len(rt.metrics) == 0:
        return {"error": "No metric definitions loaded (metrics.yaml)"}
    name_a = str(inp.get("metric_a", "")).strip()
    name_b = str(inp.get("metric_b", "")).strip()
    if name_a == name_b:
        return {"error": "metric_a 和 metric_b 必须是两个不同的指标"}
    pair = []
    for key, nm in (("metric_a", name_a), ("metric_b", name_b)):
        m = rt.metrics.get(nm)
        if m is None:
            known = ", ".join(mm.name for mm in rt.metrics.metrics)
            return {"error": f"{key} '{nm}' is not defined. Known metrics: {known}"}
        pair.append(m)
    metric_a, metric_b = pair

    try:
        days = max(14, min(int(inp.get("days") or 28), 180))
    except (TypeError, ValueError):
        return {"error": "days must be an integer"}
    try:
        end_raw = str(inp.get("end_date", "") or "").strip()
        end = parse_date(end_raw) if end_raw else date.today() - timedelta(days=1)
    except MetricError as exc:
        return {"error": str(exc)}
    start = end - timedelta(days=days - 1)

    def _daily(metric: Any) -> tuple[dict[Any, float], str]:
        sql = build_metric_series_sql(
            metric, rt.metrics, rt.store, TimeRange(start=start, end=end),
        )
        validation = validate_sql(sql, rt.store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        result = rt.executor.run(
            enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type),
            max_rows=rt.default_limit,
        )
        out: dict[Any, float] = {}
        for r in result.rows:
            if r[0] is None or r[-1] is None:
                continue
            out[parse_date(str(r[0]).strip()[:10])] = float(r[-1])
        return out, sql

    try:
        series_a, sql_a = _daily(metric_a)
        series_b, sql_b = _daily(metric_b)
    except MetricError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": _sanitize_db_error(str(exc))}

    def _value(metric: Any, series: dict, d: Any) -> float | None:
        # additive: a missing day is a true 0; ratio: undefined, drop the pair
        if d in series:
            return series[d]
        return None if metric.is_ratio else 0.0

    all_days = [start + timedelta(days=i) for i in range(days)]

    def _aligned(lag: int) -> tuple[list[float], list[float]]:
        """Pairs (a[d], b[d+lag]): positive lag means a LEADS b by lag days."""
        xs: list[float] = []
        ys: list[float] = []
        for d in all_days:
            d2 = d + timedelta(days=lag)
            if not start <= d2 <= end:
                continue
            va = _value(metric_a, series_a, d)
            vb = _value(metric_b, series_b, d2)
            if va is None or vb is None:
                continue
            xs.append(va)
            ys.append(vb)
        return xs, ys

    xs, ys = _aligned(0)
    if len(xs) < _CORR_MIN_PAIRS:
        return {
            "error": (
                f"有效对齐天数不足(需要 ≥{_CORR_MIN_PAIRS},得到 {len(xs)}),"
                "请增大 days 或确认该区间有数据"
            ),
        }
    r0 = _pearson(xs, ys)

    best: dict[str, Any] | None = None
    for lag in range(-_CORR_MAX_LAG, _CORR_MAX_LAG + 1):
        if lag == 0:
            continue
        lxs, lys = _aligned(lag)
        if len(lxs) < _CORR_MIN_PAIRS:
            continue
        r = _pearson(lxs, lys)
        if r is None:
            continue
        if best is None or abs(r) > abs(best["r"]):
            best = {"lag_days": lag, "r": round(r, 4), "n": len(lxs)}

    rt.logger.log(
        user_query=str(inp.get("user_query", "")),
        generated_sql=sql_a, status="success",
        matched_tables=[t for t in (metric_a.table, metric_b.table) if t],
        exec_time_ms=0, row_count=len(xs),
        extra={
            "source": rt.source, "kind": "correlation",
            "metric": f"{metric_a.name}~{metric_b.name}",
        },
    )
    return {
        "success": True,
        "metric_a": metric_a.name,
        "metric_b": metric_b.name,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "n_pairs": len(xs),
        "pearson_r": None if r0 is None else round(r0, 4),
        "zero_variance": r0 is None,
        "best_lag": best,
        "lag_semantics": "best_lag.lag_days > 0 表示 metric_a 领先 metric_b",
        "sql_a": sql_a,
        "sql_b": sql_b,
    }


def _attribution_execute(rt: Text2SQLRuntime, user_query: str, metric_name: str = ""):
    """Build the validated/cached/logged execute_fn for run_attribution."""

    def _check_truncated(result: QueryResult) -> None:
        # enforce_limit trims at the SQL level, so the executor never sees
        # the overflow — a row count AT the limit means the drill-down was
        # (or may have been) cut off, and contributions would silently stop
        # summing to the total change rate.
        if result.truncated or result.row_count >= rt.default_limit:
            raise MetricError(
                f"维度基数过大：下钻结果达到 {rt.default_limit} 行上限，"
                "贡献分解将不完整。请指定低基数维度（dimension 参数）重试。"
            )

    def _execute(sql: str) -> tuple[list[str], list[tuple]]:
        validation = validate_sql(sql, rt.store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)
        cached = rt.cache.get(final_sql, rt.ds_type)
        if cached is not None:
            _check_truncated(cached)
            return cached.columns, list(cached.rows)
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
        rt.cache.put(final_sql, rt.ds_type, result)
        rt.logger.log(
            user_query=user_query, generated_sql=final_sql, status="success",
            matched_tables=validation.tables,
            exec_time_ms=result.elapsed_ms, row_count=result.row_count,
            extra={"source": rt.source, "metric": metric_name, "kind": "attribution"},
        )
        _check_truncated(result)
        return result.columns, list(result.rows)

    return _execute


def _derive_prev_range(curr: Any, mode: str) -> Any:
    """Deterministic comparison-period derivation (mom/wow/yoy)."""
    from datetime import date, timedelta

    from .partition import TimeRange

    start, end = curr.start, curr.end

    def _year_back(d: date) -> date:
        try:
            return d.replace(year=d.year - 1)
        except ValueError:  # Feb 29
            return d - timedelta(days=365)

    if mode == "mom":
        span = (end - start).days + 1
        return TimeRange(start=start - timedelta(days=span),
                         end=end - timedelta(days=span))
    if mode == "wow":
        return TimeRange(start=start - timedelta(days=7),
                         end=end - timedelta(days=7))
    if mode == "yoy":
        return TimeRange(start=_year_back(start), end=_year_back(end))
    raise MetricError(f"compare_mode 只支持 mom/wow/yoy (got '{mode}')")


def _run_one_attribution(
    inp: dict[str, Any], rt: Text2SQLRuntime, metric: Any,
) -> Any:
    from .attribution import run_attribution
    from .metrics import parse_time_range

    curr_range = parse_time_range(
        str(inp.get("curr_start", "") or ""), str(inp.get("curr_end", "") or ""),
    )
    if curr_range is None:
        raise MetricError("归因分析必须提供 curr_start")
    mode = str(inp.get("compare_mode", "") or "").strip().lower()
    if mode:
        prev_range = _derive_prev_range(curr_range, mode)
    else:
        prev_range = parse_time_range(
            str(inp.get("prev_start", "") or ""), str(inp.get("prev_end", "") or ""),
        )
    if prev_range is None:
        raise MetricError("归因分析必须提供 prev_start 或 compare_mode")
    dim = str(inp.get("dimension", "") or "").strip()
    assert rt.metrics is not None  # guaranteed by _resolve_metric above
    return run_attribution(
        metric, rt.metrics, rt.store,
        _attribution_execute(rt, inp.get("user_query", ""), metric.name),
        curr_range=curr_range,
        prev_range=prev_range,
        dimensions=[dim] if dim else None,
        extra_filters=inp.get("extra_filters") or [],
        cross=bool(inp.get("cross")),
        cross_dimensions=inp.get("cross_dimensions") or None,
    )


def _publish_breakdown(rt: Text2SQLRuntime, result: Any) -> None:
    """Expose the best dimension's breakdown as the last result so the
    existing UI machinery (table, waterfall chart, CSV) picks it up."""
    from .attribution import breakdown_table

    best = next(
        (b for b in result.dimensions if b.dimension == result.best_dimension),
        None,
    )
    if best is None or not best.rows:
        return
    columns, rows = breakdown_table(best)
    rt.prev_result = rt.last_result
    rt.prev_sql = rt.last_sql
    rt.last_result = QueryResult(
        columns=columns, rows=rows, row_count=len(rows),
        truncated=False, elapsed_ms=0,
    )
    if result.sqls:
        rt.last_sql = result.sqls[-1]


def _maybe_export_report(
    inp: dict[str, Any], metric: Any, results: list, out: dict[str, Any],
    factor_split: dict[str, Any] | None = None,
) -> None:
    """Export the standalone Markdown analysis report on request."""
    if not inp.get("export_report"):
        return
    try:
        from .attribution import render_attribution_markdown
        from .exporter import _resolve_target

        text = render_attribution_markdown(
            results, title=f"{metric.display_name} 异动归因报告",
            factor_split=factor_split,
        )
        target = _resolve_target(None, f"attribution_{metric.name}", "md")
        target.write_text(text, encoding="utf-8")
        out["report_path"] = str(target.resolve())
    except Exception as exc:  # report is a bonus — never fail the analysis
        out["report_error"] = str(exc)


def _tool_run_attribution(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    from .attribution import attribution_to_dict

    metric, err = _resolve_metric(inp, rt)
    if err is not None:
        return err

    try:
        if metric.is_ratio:
            num, den = ratio_sides(metric, rt.metrics)
            num_res = _run_one_attribution(inp, rt, num)
            den_res = _run_one_attribution(inp, rt, den)
            _publish_breakdown(rt, num_res)

            def _ratio(n: float, d: float) -> float | None:
                return n / d if d else None

            from .attribution import ratio_factor_split

            prev_ratio = _ratio(num_res.prev_total, den_res.prev_total)
            curr_ratio = _ratio(num_res.curr_total, den_res.curr_total)
            split = ratio_factor_split(
                num_res.prev_total, num_res.curr_total,
                den_res.prev_total, den_res.curr_total,
            )
            out: dict[str, Any] = {
                "success": True,
                "metric": metric.name,
                "type": "ratio",
                "prev_ratio": round(prev_ratio, 6) if prev_ratio is not None else None,
                "curr_ratio": round(curr_ratio, 6) if curr_ratio is not None else None,
                "numerator": attribution_to_dict(num_res),
                "denominator": attribution_to_dict(den_res),
            }
            if split is not None:
                out["factor_split"] = {
                    k: round(v, 6) if isinstance(v, float) else v
                    for k, v in split.items()
                }
                out["note"] = (
                    "factor_split is the EXACT decomposition of the ratio's "
                    "move: numerator_effect + denominator_effect = delta "
                    "(numerator_effect = ΔN/D_curr, denominator_effect = "
                    "N_prev/D_curr - N_prev/D_prev). Lead with it, then the "
                    "per-side breakdowns."
                )
            else:
                out["note"] = (
                    "Two-factor split undefined (a period's denominator is 0); "
                    "present the numerator/denominator movements side by side."
                )
            _maybe_export_report(inp, metric, [num_res, den_res], out,
                                 factor_split=split)
            return out

        result = _run_one_attribution(inp, rt, metric)
        _publish_breakdown(rt, result)
        out = {"success": True, "type": "additive", **attribution_to_dict(result)}
        _maybe_export_report(inp, metric, [result], out)
        return out
    except MetricError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Attribution failed: {_sanitize_db_error(str(exc))}"}


def _tool_trace_metric(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Metric provenance: caliber level + lineage upstream chain."""
    import os

    metric, err = _resolve_metric(inp, rt)
    if err is not None:
        return err
    depth = max(1, min(int(inp.get("depth", 3) or 3), 10))

    # caliber level (always available)
    assert rt.metrics is not None  # guaranteed by _resolve_metric above
    if metric.is_ratio:
        maybe = [rt.metrics.get(metric.numerator), rt.metrics.get(metric.denominator)]
        parts = [p for p in maybe if p is not None and not p.is_ratio]
    else:
        parts = [metric]
    out: dict[str, Any] = {
        "success": True,
        "metric": _metric_payload(metric),
        "sources": [
            {"metric": p.name, "table": p.table, "expression": p.expression,
             "default_filters": list(p.default_filters)}
            for p in parts
        ],
    }

    sql_dir = os.getenv("T2S_LINEAGE_SQL_DIR", "").strip()
    if not sql_dir:
        out["note"] = (
            "上游血缘链未启用：设置 T2S_LINEAGE_SQL_DIR 指向数仓 SQL 目录后，"
            "trace_metric 会附带每张来源表的上游加工链路。当前仅返回口径层。"
        )
        return out

    try:
        graph = rt._lineage_graph
        if graph is None or getattr(rt, "_lineage_dir", "") != sql_dir:
            from seatunnel_agent.agents.data.data_lineage.loaders import build_graph

            graph, warnings = build_graph(sql_dir=sql_dir)
            rt._lineage_graph = graph
            rt._lineage_dir = sql_dir
            if warnings:
                out["lineage_warnings"] = warnings[:5]
        chains = []
        for p in parts:
            chain = graph.upstream_of(p.table, depth=depth)
            chains.append({
                "table": p.table,
                "missing_in_graph": chain.missing_root,
                "upstream_count": chain.upstream_count,
                "upstream": sorted(
                    (
                        {"table": t, "depth": -d}
                        for t, d in chain.depth_of.items()
                        if t != chain.root and d < 0
                    ),
                    key=lambda x: (x["depth"], x["table"]),
                ),
                "edges": [list(e) for e in chain.edges][:50],
                "truncated": chain.truncated,
            })
        out["lineage"] = chains
    except Exception as exc:
        out["lineage_error"] = f"血缘图构建失败: {exc}"
    return out
