"""SQL-execution tool handlers and shared result builders for the
Text2SQL agent: execute/explain plus static review, skew and transpile."""

from __future__ import annotations

from typing import Any

from .executor import PARTITION_ENGINES, QueryResult
from .partition import has_partition_filter
from .quality import check_quality
from .runtime import (
    Text2SQLRuntime,
    _sanitize_db_error,
    _suggest_column,
    classify_error,
)
from .validator import ValidationResult, enforce_limit, validate_sql

_PREVIEW_ROWS = 20


def _build_sql_error(rt: Text2SQLRuntime, error_msg: str, **extra: Any) -> dict[str, Any]:
    """Increment retry counter and build a structured error response."""
    rt.sql_retries += 1
    error_type, retry_hint = classify_error(error_msg)
    err: dict[str, Any] = {
        "error": error_msg,
        "error_type": error_type,
        "retry_hint": retry_hint,
        "attempt": rt.sql_retries,
        **extra,
    }
    if rt.sql_retries >= rt.max_sql_retries:
        err["max_retries_reached"] = True
    return err


def _log_and_reject(
    rt: Text2SQLRuntime, user_query: str, sql: str,
    tables: list[str], error_msg: str, status: str = "rejected",
) -> dict[str, Any]:
    """Log a failed SQL attempt and return a structured error."""
    rt.logger.log(
        user_query=user_query, generated_sql=sql, status=status,
        matched_tables=tables, error=error_msg,
        extra={"source": rt.source},
    )
    extra: dict[str, Any] = {"sql": sql} if status == "error" else {}
    return _build_sql_error(rt, error_msg, **extra)


def _cost_hints(sql: str, rt: Text2SQLRuntime) -> list[dict[str, Any]]:
    """Pre-execution scan-cost advisories (partition engines only).

    ``T2S_COST_WARN_PARTITIONS`` tunes the width threshold (default 90)."""
    import os

    if rt.ds_type not in PARTITION_ENGINES:
        return []
    from .partition import scan_cost_hints

    try:
        warn = int(os.getenv("T2S_COST_WARN_PARTITIONS", "") or 90)
    except ValueError:
        warn = 90
    try:
        return scan_cost_hints(sql, rt.store, warn_partitions=warn)
    except Exception:
        return []  # advisories must never break execution


def _cost_block(hints: list[dict[str, Any]]) -> str | None:
    """Optional hard stop: ``T2S_COST_BLOCK_PARTITIONS=N`` rejects queries
    whose estimated partition count reaches N (unset = advise only)."""
    import os

    raw = os.getenv("T2S_COST_BLOCK_PARTITIONS", "").strip()
    if not raw:
        return None
    try:
        limit = int(raw)
    except ValueError:
        return None
    worst = max(
        (h["estimated_partitions"] for h in hints
         if h.get("estimated_partitions")),
        default=None,
    )
    if worst is not None and worst >= limit:
        return (
            f"查询预计扫描约 {worst} 个分区,达到 T2S_COST_BLOCK_PARTITIONS="
            f"{limit} 的硬拦截阈值。请缩小时间范围后重试。"
        )
    return None


def _check_partition_filters(sql: str, validation: ValidationResult, rt: Text2SQLRuntime) -> str | None:
    """Return an error message if any partitioned table lacks a partition filter."""
    if rt.ds_type not in PARTITION_ENGINES:
        return None
    missing = []
    for tname in validation.tables:
        table = rt.store.get(tname)
        if table and table.is_partitioned:
            pcol = table.partition_columns[0].name
            if not has_partition_filter(sql, pcol):
                missing.append(f"{table.full_name} (partition column: {pcol})")
    if missing:
        return (
            "Partitioned table(s) missing partition filter: "
            + ", ".join(missing)
            + ". Add a WHERE condition on the partition column "
            "(use get_max_partition if no time range was given)."
        )
    return None


def _build_success(
    result: QueryResult, sql: str,
    validation: ValidationResult, **extra: Any,
) -> dict[str, Any]:
    """Build a structured success response for execute_sql."""
    from .masking import apply_masking

    preview, masked_cols = apply_masking(
        result.columns, result.rows[:_PREVIEW_ROWS], sql=sql,
    )
    out: dict[str, Any] = {
        "success": True,
        "sql": sql,
        "columns": result.columns,
        "preview_rows": [list(r) for r in preview],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "elapsed_ms": result.elapsed_ms,
        **extra,
    }
    if masked_cols:
        out["masked_columns"] = masked_cols
    if validation.column_warnings:
        out["column_warnings"] = validation.column_warnings
    report = check_quality(result.columns, result.rows)
    if report.has_warnings:
        out["quality_warnings"] = [
            {"column": w.column, "warning_type": w.warning_type, "detail": w.detail}
            for w in report.warnings
        ]
    return out


# ds_type -> sql_review linter dialect (module integration: free safety net)
_REVIEW_DIALECT_BY_DS = {
    "hive": "hive", "sparksql": "spark", "flinksql": "flink",
    "mysql": "mysql", "postgresql": "postgresql", "sqlserver": "sqlserver",
    "clickhouse": "clickhouse", "doris": "doris", "sqlite": "sqlite",
}

# ds_type -> data_skew detector dialect (batch warehouses only)
_SKEW_DIALECT_BY_DS = {"hive": "hive", "sparksql": "spark"}

_SLOW_QUERY_MS_DEFAULT = 5000


def _review_findings(sql: str, rt: Text2SQLRuntime) -> list[dict[str, Any]]:
    """Static SQL-review pre-flight (critical/risk only, capped, never raises)."""
    dialect = _REVIEW_DIALECT_BY_DS.get(rt.ds_type)
    if dialect is None:
        return []
    try:
        from seatunnel_agent.agents.data.sql_review.linter import lint_sql
        from seatunnel_agent.agents.data.sql_review.report import Severity

        findings = lint_sql(sql, dialect=dialect, store=rt.store)
        picked = [
            f for f in findings
            if f.severity in (Severity.CRITICAL, Severity.RISK)
        ][:5]
        return [
            {
                "severity": f.severity.value,
                "category": f.category,
                "location": f.location,
                "description": f.description,
                "suggestion": f.suggestion,
            }
            for f in picked
        ]
    except Exception:
        return []  # advisory only — never block execution


def _skew_hints(sql: str, rt: Text2SQLRuntime, elapsed_ms: int) -> list[dict[str, Any]]:
    """Data-skew advice for slow batch-engine queries (never raises)."""
    dialect = _SKEW_DIALECT_BY_DS.get(rt.ds_type)
    if dialect is None:
        return []
    try:
        import os

        threshold = int(os.getenv("T2S_SLOW_QUERY_MS", _SLOW_QUERY_MS_DEFAULT))
    except ValueError:
        threshold = _SLOW_QUERY_MS_DEFAULT
    if elapsed_ms < threshold:
        return []
    try:
        from seatunnel_agent.agents.data.data_skew.detector import detect_skew

        findings, _hints = detect_skew(sql, dialect=dialect)
        return [
            {
                "severity": f.severity.value,
                "category": f.category,
                "description": f.description,
                "suggestion": f.suggestion,
            }
            for f in findings[:3]
        ]
    except Exception:
        return []


def _tool_review_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the sql_review static linter."""
    sql = str(inp.get("sql", "")).strip()
    if not sql:
        return {"error": "No SQL provided"}
    dialect = str(inp.get("dialect", "") or "").strip().lower() \
        or _REVIEW_DIALECT_BY_DS.get(rt.ds_type, "hive")
    try:
        from seatunnel_agent.agents.data.sql_review.linter import (
            is_known_dialect,
            lint_sql,
        )

        if not is_known_dialect(dialect):
            return {"error": f"Unknown review dialect '{dialect}'"}
        findings = lint_sql(sql, dialect=dialect, store=rt.store)
    except Exception as exc:
        return {"error": f"Review failed: {exc}"}
    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
    return {
        "success": True,
        "dialect": dialect,
        "counts": by_sev,
        "findings": [
            {
                "severity": f.severity.value,
                "category": f.category,
                "location": f.location,
                "description": f.description,
                "impact": f.impact,
                "suggestion": f.suggestion,
            }
            for f in findings[:20]
        ],
        "truncated": len(findings) > 20,
    }


def _tool_skew_check(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the data_skew static analyzer."""
    sql = str(inp.get("sql", "")).strip()
    if not sql:
        return {"error": "No SQL provided"}
    dialect = str(inp.get("dialect", "") or "").strip().lower() \
        or _SKEW_DIALECT_BY_DS.get(rt.ds_type, "spark")
    try:
        from seatunnel_agent.agents.data.data_skew.agent import static_skew_report
        from seatunnel_agent.agents.data.data_skew.report import render_report

        report = static_skew_report(sql, dialect=dialect)
        return {
            "success": True,
            "dialect": report.dialect,
            "finding_count": len(report.findings),
            "report_markdown": render_report(report, "zh"),
        }
    except Exception as exc:
        return {"error": f"Skew analysis failed: {exc}"}


def _tool_transpile_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the deterministic dialect translator."""
    sql = str(inp.get("sql", "")).strip()
    target = str(inp.get("target_dialect", "")).strip().lower()
    if not sql or not target:
        return {"error": "sql and target_dialect are required"}
    source = str(inp.get("source_dialect", "") or "").strip().lower() or None
    try:
        from seatunnel_agent.agents.data.sql_transpile.i18n import issue_message
        from seatunnel_agent.agents.data.sql_transpile.transpiler import translate

        result = translate(sql, dst=target, src=source)
    except Exception as exc:
        return {"error": f"Translation failed: {exc}"}
    return {
        "success": True,
        "src_dialect": result.src_dialect,
        "dst_dialect": result.dst_dialect,
        "src_inferred": result.src_inferred,
        "counts": result.counts(),
        "statements": [
            {
                "line": s.line,
                "output_sql": s.output_sql,
                "issues": [
                    {
                        "kind": i.kind,
                        "level": i.level,
                        "message": issue_message("zh", i.kind, i.params),
                    }
                    for i in s.issues[:10]
                ],
            }
            for s in result.statements[:20]
        ],
    }


def _tool_execute_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    sql = inp.get("sql", "")
    user_query = inp.get("user_query", "")

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return _log_and_reject(
            rt, user_query, sql, validation.tables,
            "SQL rejected: " + "; ".join(validation.errors),
        )

    partition_err = _check_partition_filters(sql, validation, rt)
    if partition_err:
        return _log_and_reject(rt, user_query, sql, validation.tables, partition_err)

    cost_hints = _cost_hints(sql, rt)
    block_err = _cost_block(cost_hints)
    if block_err:
        return _log_and_reject(rt, user_query, sql, validation.tables, block_err)

    final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)

    cached = rt.cache.get(final_sql, rt.ds_type)
    if cached is not None:
        rt.sql_retries = 0
        rt.prev_result = rt.last_result
        rt.prev_sql = rt.last_sql
        rt.last_result = cached
        rt.last_sql = final_sql
        rt.logger.log(
            user_query=user_query, generated_sql=final_sql, status="cache_hit",
            matched_tables=validation.tables,
            exec_time_ms=0, row_count=cached.row_count,
            extra={"source": rt.source},
        )
        return _build_success(cached, final_sql, validation, cached=True, elapsed_ms=0)

    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        err = _log_and_reject(
            rt, user_query, final_sql, validation.tables,
            f"Execution failed: {_sanitize_db_error(str(exc))}", status="error",
        )
        suggestion = _suggest_column(str(exc), rt)
        if suggestion:
            err["suggestion"] = suggestion
        return err

    rt.sql_retries = 0
    rt.prev_result = rt.last_result
    rt.prev_sql = rt.last_sql
    rt.last_result = result
    rt.last_sql = final_sql
    rt.cache.put(final_sql, rt.ds_type, result)
    rt.logger.log(
        user_query=user_query, generated_sql=final_sql, status="success",
        matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": rt.source},
    )
    out = _build_success(result, final_sql, validation)
    # Cross-module advisories (free safety nets — never block, never raise):
    findings = _review_findings(sql, rt)
    if findings:
        out["review_findings"] = findings
    hints = _skew_hints(sql, rt, result.elapsed_ms)
    if hints:
        out["skew_hints"] = hints
    if cost_hints:
        out["cost_hints"] = cost_hints
    if rt.prev_result is not None:
        from .differ import diff_results
        diff = diff_results(
            rt.prev_result.columns, rt.prev_result.rows,
            result.columns, result.rows,
        )
        if diff.has_changes:
            out["diff"] = {
                "added_count": len(diff.added_rows),
                "removed_count": len(diff.removed_rows),
                "cols_added": diff.columns_added,
                "cols_removed": diff.columns_removed,
                "old_count": diff.old_count,
                "new_count": diff.new_count,
            }
    return out


_EXPLAIN_UNSUPPORTED = frozenset({"sqlserver"})


def _tool_explain_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    sql = inp.get("sql", "").strip()
    if not sql:
        return {"error": "No SQL provided"}
    if rt.ds_type in _EXPLAIN_UNSUPPORTED:
        return {"error": f"EXPLAIN is not supported for {rt.ds_type}"}

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return {"error": "SQL rejected: " + "; ".join(validation.errors)}

    try:
        result = rt.executor.run(f"EXPLAIN {sql}", max_rows=200)
    except Exception as exc:
        return {"error": f"EXPLAIN failed: {_sanitize_db_error(str(exc))}"}

    plan_lines = []
    for row in result.rows:
        plan_lines.append(" | ".join(str(v) for v in row))
    return {
        "success": True,
        "sql": sql,
        "plan": "\n".join(plan_lines),
        "columns": result.columns,
    }
