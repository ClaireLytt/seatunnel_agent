"""Metric-family tool handlers for the Text2SQL agent: matching, caliber
expansion, forecasting, attribution and provenance tracing."""

from __future__ import annotations

from typing import Any

from .executor import QueryResult
from .metrics import (
    MetricError,
    build_metric_sql,
    build_metric_series_sql,
    parse_date,
    ratio_sides,
    parse_time_range,
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

    try:
        horizon = max(1, min(int(inp.get("horizon_days") or 7), 30))
        history = max(14, min(int(inp.get("history_days") or 28), 180))
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

    try:
        fc = forecast_series(
            points, horizon=horizon,
            fill="ffill" if metric.is_ratio else "zero",
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

    def _year_back(d: "date") -> "date":
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
) -> "Any":
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
    if metric.is_ratio:
        parts = [rt.metrics.get(metric.numerator), rt.metrics.get(metric.denominator)]
        parts = [p for p in parts if p is not None and not p.is_ratio]
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
