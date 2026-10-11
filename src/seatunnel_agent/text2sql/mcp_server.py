# -*- coding: utf-8 -*-
"""MCP server exposing Chat BI's deterministic primitives over stdio.

Start with ``seatunnel-agent t2s-mcp`` and register it in an MCP client
(Claude Desktop / Claude Code / Cline). Mirrors the lineage/skew MCP
servers' shape: tool callables are plain functions built by
:func:`build_tool_functions`, usable and testable without the ``mcp``
package; :func:`create_mcp_server` only wires them into FastMCP.

Design (PRD §7): the external agent IS an LLM already, so this server
exposes only deterministic atoms — schema lookup, hybrid table retrieval,
the metric catalog and its deterministic SQL expansion. SQL execution is
OFF by default (``--allow-execute`` opts in; SELECT-only validator +
enforced LIMIT still apply), and credentials are resolved server-side
from environment variables / the sqlite path — never from MCP arguments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

_INSTRUCTIONS = (
    "Chat BI（Text2SQL）确定性原子能力：表结构查询、混合表检索（关键词+BM25"
    "+可选向量）、业务指标口径目录、指标 SQL 的确定性展开（同参数永远同 SQL，"
    "保证口径一致）。execute_readonly_sql 默认关闭，开启后也仅允许白名单表上的"
    "SELECT 且强制 LIMIT。"
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def build_tool_functions(
    ddl_path: str = "",
    metrics_path: str = "",
    ds_type: str = "hive",
    allow_execute: bool = False,
    database: str = "",
) -> dict[str, Callable[..., str]]:
    """Chat BI tool callables keyed by name. All return strings (JSON)."""
    from .executor import schema_ddl_path_from_env
    from .metrics import load_metric_store
    from .retrieval import HybridRetriever
    from .schema import SchemaStore

    ddl = Path(ddl_path) if ddl_path else Path(schema_ddl_path_from_env())
    if not ddl.is_file():
        raise RuntimeError(f"schema DDL 文件不存在: {ddl}")
    schema_store = SchemaStore.from_file(ddl)
    if len(schema_store) == 0:
        raise RuntimeError(f"schema DDL 未解析出任何表: {ddl}")
    metric_store, metric_errors = load_metric_store(
        schema_store, path=metrics_path or None,
    )
    if metric_errors:
        raise RuntimeError("指标定义无效: " + "; ".join(metric_errors))
    retriever = HybridRetriever(schema_store)

    def list_tables() -> str:
        """列出全部可查询的表（白名单）：表名、中文注释、列数、增量/全量类型。"""
        return _json({
            "count": len(schema_store),
            "tables": [
                {
                    "table": t.full_name,
                    "comment": t.comment,
                    "columns": len(t.columns),
                    "table_type": t.table_type,
                }
                for t in schema_store.tables
            ],
        })

    def get_table_schema(table: str) -> str:
        """查询单表结构：全部列（类型/中文注释）、分区列、表类型。"""
        t = schema_store.get(table)
        if t is None:
            return _json({"error": f"表 '{table}' 不在 schema 白名单中"})
        return _json({
            "table": t.full_name,
            "comment": t.comment,
            "table_type": t.table_type,
            "partition_columns": [
                {"name": c.name, "type": c.dtype, "comment": c.comment}
                for c in t.partition_columns
            ],
            "columns": [
                {"name": c.name, "type": c.dtype, "comment": c.comment}
                for c in t.columns
            ],
        })

    def match_tables(query: str, top_n: int = 5) -> str:
        """按自然语言问题检索候选表（关键词+BM25+可选向量的混合排序）。"""
        top_n = max(1, min(int(top_n), 20))
        matches = retriever.rank(query, top_n=top_n)
        return _json({
            "count": len(matches),
            "candidates": [
                {
                    "table": m.table.full_name,
                    "comment": m.table.comment,
                    "score": m.score,
                    "matched_columns": list(dict.fromkeys(m.column_hits))[:10],
                }
                for m in matches
            ],
        })

    def match_metrics(query: str) -> str:
        """按自然语言问题检索已定义的业务指标（含口径说明）。"""
        if len(metric_store) == 0:
            return _json({"count": 0, "note": "未配置指标定义 (metrics.yaml)"})
        matches = metric_store.match(query, top_n=5)
        return _json({
            "count": len(matches),
            "candidates": [
                {
                    "name": r.metric.name,
                    "display_name": r.metric.display_name,
                    "description": r.metric.description,
                    "type": r.metric.metric_type,
                    "score": round(r.score, 2),
                }
                for r in matches
            ],
        })

    def explain_metric(name: str) -> str:
        """查看单个指标的完整口径定义：表/表达式/维度/恒定过滤/负责人。"""
        m = metric_store.get(name)
        if m is None:
            known = ", ".join(x.name for x in metric_store.metrics) or "(无)"
            return _json({"error": f"指标 '{name}' 未定义。已知指标: {known}"})
        payload: dict[str, Any] = {
            "name": m.name,
            "display_name": m.display_name,
            "aliases": list(m.aliases),
            "description": m.description,
            "type": m.metric_type,
            "unit": m.unit,
            "owner": m.owner,
        }
        if m.is_ratio:
            payload.update(numerator=m.numerator, denominator=m.denominator)
        else:
            payload.update(
                table=m.table, expression=m.expression,
                time_column=m.time_column,
                dimensions=list(m.dimensions),
                default_filters=list(m.default_filters),
            )
        return _json(payload)

    def metric_sql(
        metric: str,
        dimensions: str = "",
        start_date: str = "",
        end_date: str = "",
        max_partition: str = "",
        extra_filters: str = "",
    ) -> str:
        """确定性展开指标 SQL（同参数永远同 SQL，不执行）。dimensions/
        extra_filters 用分号分隔多个；日期支持 YYYY-MM-DD / yyyyMMdd。"""
        from .metrics import MetricError, build_metric_sql, parse_time_range

        m = metric_store.get(metric)
        if m is None:
            known = ", ".join(x.name for x in metric_store.metrics) or "(无)"
            return _json({"error": f"指标 '{metric}' 未定义。已知指标: {known}"})
        try:
            sql = build_metric_sql(
                m, metric_store, schema_store,
                dimensions=[d for d in dimensions.split(";") if d.strip()],
                time_range=parse_time_range(start_date, end_date),
                max_partition=max_partition.strip() or None,
                extra_filters=[f for f in extra_filters.split(";") if f.strip()],
            )
        except MetricError as exc:
            return _json({"error": str(exc)})
        return _json({"metric": m.name, "sql": sql})

    _lineage_cache: dict[str, Any] = {}

    def trace_metric(metric: str, depth: int = 3) -> str:
        """指标溯源：口径层（来源表/表达式/恒定过滤）+ 血缘图上游加工链路
        （需服务端配置 T2S_LINEAGE_SQL_DIR，未配置时仅返回口径层）。"""
        import os

        m = metric_store.get(metric)
        if m is None:
            known = ", ".join(x.name for x in metric_store.metrics) or "(无)"
            return _json({"error": f"指标 '{metric}' 未定义。已知指标: {known}"})
        depth = max(1, min(int(depth), 10))
        if m.is_ratio:
            parts = [metric_store.get(m.numerator), metric_store.get(m.denominator)]
            parts = [p for p in parts if p is not None and not p.is_ratio]
        else:
            parts = [m]
        out: dict[str, Any] = {
            "metric": m.name,
            "sources": [
                {"metric": p.name, "table": p.table, "expression": p.expression,
                 "default_filters": list(p.default_filters)}
                for p in parts
            ],
        }
        sql_dir = os.getenv("T2S_LINEAGE_SQL_DIR", "").strip()
        if not sql_dir:
            out["note"] = "上游血缘链未启用（服务端未配置 T2S_LINEAGE_SQL_DIR）"
            return _json(out)
        try:
            graph = _lineage_cache.get(sql_dir)
            if graph is None:
                from ..data_lineage.loaders import build_graph

                graph, _warns = build_graph(sql_dir=sql_dir)
                _lineage_cache[sql_dir] = graph
            out["lineage"] = []
            for p in parts:
                chain = graph.upstream_of(p.table, depth=depth)
                out["lineage"].append({
                    "table": p.table,
                    "missing_in_graph": chain.missing_root,
                    "upstream": sorted(
                        ({"table": t, "depth": -d}
                         for t, d in chain.depth_of.items()
                         if t != chain.root and d < 0),
                        key=lambda x: (x["depth"], x["table"]),
                    ),
                    "edges": [list(e) for e in chain.edges][:50],
                })
        except Exception as exc:
            out["lineage_error"] = f"血缘图构建失败: {exc}"
        return _json(out)

    tools: dict[str, Callable[..., str]] = {
        "list_tables": list_tables,
        "get_table_schema": get_table_schema,
        "match_tables": match_tables,
        "match_metrics": match_metrics,
        "explain_metric": explain_metric,
        "metric_sql": metric_sql,
        "trace_metric": trace_metric,
    }

    if allow_execute:
        from .executor import DatabaseConfig, config_from_env, create_executor
        from .validator import enforce_limit, validate_sql

        def _db_config() -> "DatabaseConfig | None":
            if ds_type == "sqlite":
                return DatabaseConfig(
                    ds_type="sqlite", host="", port=0, database=database,
                )
            return config_from_env(ds_type)

        def execute_readonly_sql(sql: str) -> str:
            """执行 SELECT（白名单表 + 强制 LIMIT + 只读校验）。连接凭据来自
            服务端环境变量，不接受参数传入。"""
            from .tools import _sanitize_db_error

            validation = validate_sql(sql, schema_store)
            if not validation.ok:
                return _json({"error": "SQL rejected: " + "; ".join(validation.errors)})
            final_sql = enforce_limit(sql, dialect=ds_type)
            db_config = _db_config()
            if db_config is None:
                return _json({
                    "error": "未配置数据库连接（设置对应环境变量，如 HIVE_HOST）"
                })
            try:
                result = create_executor(db_config).run(final_sql, max_rows=1000)
            except Exception as exc:
                return _json({"error": _sanitize_db_error(str(exc))})
            from .qlog import QueryLogger
            QueryLogger().log(
                user_query="[mcp] execute_readonly_sql", generated_sql=final_sql,
                status="success", matched_tables=validation.tables,
                exec_time_ms=result.elapsed_ms, row_count=result.row_count,
                extra={"source": "mcp"},
            )
            return _json({
                "sql": final_sql,
                "columns": result.columns,
                "rows": [list(r) for r in result.rows[:100]],
                "row_count": result.row_count,
                "elapsed_ms": result.elapsed_ms,
            })

        tools["execute_readonly_sql"] = execute_readonly_sql

        def metric_attribution(
            metric: str,
            curr_start: str,
            prev_start: str,
            curr_end: str = "",
            prev_end: str = "",
            dimension: str = "",
        ) -> str:
            """指标异动归因：两期总量对比 + 逐维度贡献分解（贡献率之和恒等于
            总变动率）。日期支持 YYYY-MM-DD / yyyyMMdd；dimension 省略时自动
            遍历允许维度。查询预算 2+2K 条 SQL。"""
            from .attribution import attribution_to_dict, run_attribution
            from .metrics import MetricError, parse_time_range
            from .tools import _sanitize_db_error

            m = metric_store.get(metric)
            if m is None:
                known = ", ".join(x.name for x in metric_store.metrics) or "(无)"
                return _json({"error": f"指标 '{metric}' 未定义。已知指标: {known}"})
            db_config = _db_config()
            if db_config is None:
                return _json({"error": "未配置数据库连接（设置对应环境变量）"})
            executor = create_executor(db_config)

            def _execute(sql: str):
                validation = validate_sql(sql, schema_store)
                if not validation.ok:
                    raise MetricError(
                        "SQL rejected: " + "; ".join(validation.errors))
                result = executor.run(
                    enforce_limit(sql, dialect=ds_type), max_rows=1000)
                if result.truncated or result.row_count >= 1000:
                    raise MetricError("维度基数过大：下钻结果达到 1000 行上限")
                return result.columns, list(result.rows)

            def _attribute_raw(target):
                return run_attribution(
                    target, metric_store, schema_store, _execute,
                    curr_range=parse_time_range(curr_start, curr_end),
                    prev_range=parse_time_range(prev_start, prev_end),
                    dimensions=[dimension] if dimension.strip() else None,
                )

            try:
                if m.is_ratio:
                    from .attribution import ratio_factor_split

                    num_res = _attribute_raw(metric_store.get(m.numerator))
                    den_res = _attribute_raw(metric_store.get(m.denominator))
                    out = {
                        "metric": m.name, "type": "ratio",
                        "numerator": attribution_to_dict(num_res),
                        "denominator": attribution_to_dict(den_res),
                    }
                    split = ratio_factor_split(
                        num_res.prev_total, num_res.curr_total,
                        den_res.prev_total, den_res.curr_total,
                    )
                    if split is not None:
                        out["factor_split"] = {
                            k: round(v, 6) if isinstance(v, float) else v
                            for k, v in split.items()
                        }
                    return _json(out)
                return _json({
                    "type": "additive",
                    **attribution_to_dict(_attribute_raw(m)),
                })
            except MetricError as exc:
                return _json({"error": str(exc)})
            except Exception as exc:
                return _json({"error": _sanitize_db_error(str(exc))})

        tools["metric_attribution"] = metric_attribution

    return tools


def create_mcp_server(
    ddl_path: str = "",
    metrics_path: str = "",
    ds_type: str = "hive",
    allow_execute: bool = False,
    database: str = "",
):
    """FastMCP server (stdio) wrapping the Chat BI tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "未安装 mcp 依赖，请先执行: pip install 'seatunnel-agent[mcp]'"
        ) from exc

    server = FastMCP("seatunnel-chatbi", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        ddl_path=ddl_path, metrics_path=metrics_path, ds_type=ds_type,
        allow_execute=allow_execute, database=database,
    )
    for fn in functions.values():
        server.tool()(fn)
    return server
