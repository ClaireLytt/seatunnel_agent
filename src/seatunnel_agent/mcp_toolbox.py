# -*- coding: utf-8 -*-
"""Unified MCP toolbox: the whole agent suite as one stdio MCP server.

``seatunnel-agent mcp`` exposes the deterministic capabilities of every
agent — SQL review, dialect translation, data-skew analysis, change-impact
diff, DataX/Sqoop migration, plus schema browsing / read-only querying /
table comparison over the shared saved-connection store — to any MCP
client (Claude Code / Claude Desktop / Cline / Cursor).

Design rules (see docs/mcp_toolbox.md):

- **Deterministic only.** No tool here calls an LLM: the caller IS the
  LLM. Static review, transpile, skew scan, impact diff and migration are
  pure functions; results are reproducible and cost zero tokens.
- **Named connections, never credentials.** Database tools take the NAME
  of a connection saved on the Settings page (shared
  ``ConnectionPresetsStore``); passwords never travel through tool args
  or the model context.
- **Read-only execution.** ``run_query`` accepts a single SELECT/WITH
  statement only (the data-skew consistency guard) and caps rows at
  ``MAX_QUERY_ROWS``.
- **Errors are strings.** Tools return a readable message instead of
  raising — an MCP client shows the text either way, and a traceback
  helps nobody.

Like the per-agent servers, the tool callables are plain functions built
by :func:`build_tool_functions` (usable and testable without the ``mcp``
package); :func:`create_mcp_server` only wires them into FastMCP.
"""

from __future__ import annotations

import re
import threading
from typing import Any, Callable

MAX_QUERY_ROWS = 500

_INSTRUCTIONS = (
    "SeaTunnel Agent 大数据 SQL 工具箱：SQL 审查（静态规则）、方言翻译"
    "（hive/spark/doris/starrocks/mysql/presto/clickhouse）、数据倾斜分析、"
    "SQL 变更影响分析、DataX/Sqoop→SeaTunnel 配置迁移；并可通过已保存的"
    "数据库连接（按名称引用，不经手密码）浏览表结构、只读查询、跨库比对行数"
    "与表结构。全部工具均为确定性实现：不调用 LLM，除只读查询外不执行 SQL。"
)

_SIMPLE_TABLE_RE = re.compile(r"[A-Za-z_][\w.]*\Z")


def _fmt_rows(columns: list[str], rows: list[tuple]) -> str:
    """Small markdown table (values pipe-escaped, capped at 200 chars/cell)."""
    def cell(v: Any) -> str:
        s = "NULL" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= 200 else s[:199] + "…"

    head = "| " + " | ".join(cell(c) for c in columns) + " |"
    sep = "|" + "---|" * len(columns)
    body = ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def build_tool_functions(
    default_lang: str = "zh",
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    sql_dialect: str = "hive",
) -> dict[str, Callable[..., str]]:
    """All toolbox callables keyed by tool name.

    Lineage tools are included only when a lineage source (*sql_dir*,
    *seatunnel_dir* or *use_hive*) is configured — they need a graph.
    """
    tools: dict[str, Callable[..., str]] = {}

    def _lang(lang: str) -> str:
        lg = (lang or default_lang).strip().lower()
        return "en" if lg.startswith("en") else "zh"

    # ── pure-static analysis tools ──────────────────────────────────────

    def sql_review(sql: str, dialect: str = "hive", ddl: str = "",
                   lang: str = "") -> str:
        """SQL 静态审查：性能/质量/规范规则（分区裁剪、SELECT *、隐式转换、
        时间边界等），返回严重度分级的 Markdown 报告。dialect 支持
        hive/spark/flink/maxcompute/mysql/postgresql/clickhouse/doris/
        starrocks/sqlite；ddl 可选（CREATE TABLE 语句，启用 schema 校验）。"""
        from .sql_review.agent import static_review_report
        from .sql_review.linter import is_known_dialect, normalize_dialect
        from .sql_review.report import render_report

        if not (sql or "").strip():
            return "SQL 不能为空 / SQL must not be empty"
        if not is_known_dialect(dialect):
            return f"未知方言 / unknown dialect: {dialect}"
        store = None
        if (ddl or "").strip():
            from .text2sql.schema import SchemaStore, parse_ddl
            try:
                store = SchemaStore(parse_ddl(ddl))
            except Exception as exc:  # noqa: BLE001 — surface as text
                return f"DDL 解析失败 / DDL parse failed: {exc}"
        rep = static_review_report(sql, normalize_dialect(dialect), store=store)
        return render_report(rep, lang=_lang(lang))

    def sql_transpile(sql: str, to_dialect: str, from_dialect: str = "",
                      lang: str = "") -> str:
        """SQL 方言翻译（确定性，基于 sqlglot，不执行 SQL）：返回翻译后的
        SQL 与不兼容点清单（解析失败/不支持语法/未知 UDF/存储子句等）。
        to_dialect 如 doris/starrocks/spark/hive/mysql/presto/clickhouse；
        from_dialect 留空则自动推断。"""
        from .sql_transpile.report import render_markdown
        from .sql_transpile.transpiler import translate

        if not (sql or "").strip():
            return "SQL 不能为空 / SQL must not be empty"
        try:
            result = translate(sql, dst=to_dialect,
                               src=(from_dialect or None))
        except Exception as exc:  # noqa: BLE001 — unknown dialect etc.
            return f"翻译失败 / translation failed: {exc}"
        return render_markdown(result, lang=_lang(lang))

    def impact_diff(old_sql: str, new_sql: str, dialect: str = "hive",
                    lang: str = "") -> str:
        """SQL 变更影响分析：对比两段 SQL（旧版 vs 新版），输出表级/字段级
        变更、严重度分级（error/warn/info）与下游影响面的 Markdown 报告。
        适合在改动上线前评估 blast radius。"""
        from .data_lineage.impact import analyze_sql_texts, render_impact_markdown

        try:
            result = analyze_sql_texts(old_sql, new_sql, sql_dialect=dialect)
        except ValueError as exc:
            return str(exc)
        return render_impact_markdown(result, lang=_lang(lang))

    def migrate_to_seatunnel(content: str, source_kind: str = "auto",
                             lang: str = "") -> str:
        """DataX job JSON 或 sqoop 命令 → SeaTunnel HOCON 配置，附迁移说明
        清单（不支持项/需人工确认项）。source_kind: auto | datax | sqoop。"""
        from .config_migrate.migrator import migrate_datax, migrate_sqoop
        from .config_migrate.report import render_migrate_markdown

        text = (content or "").strip()
        if not text:
            return "内容不能为空 / content must not be empty"
        kind = (source_kind or "auto").strip().lower()
        if kind == "auto":
            kind = "datax" if text.lstrip().startswith("{") else "sqoop"
        if kind == "datax":
            res = migrate_datax(text)
        elif kind == "sqoop":
            res = migrate_sqoop(text)
        else:
            return f"source_kind 必须是 auto/datax/sqoop，收到: {source_kind}"
        return render_migrate_markdown(res, lang=_lang(lang))

    tools.update(sql_review=sql_review, sql_transpile=sql_transpile,
                 impact_diff=impact_diff,
                 migrate_to_seatunnel=migrate_to_seatunnel)

    # data-skew tools (already factored for MCP) — history source stays 'mcp'
    from .data_skew.mcp_server import build_tool_functions as _skew_tools
    tools.update(_skew_tools(default_lang=default_lang))

    # ── database tools over NAMED saved connections ─────────────────────
    # (shared store with the Settings / Data Comparison pages; passwords
    # stay in the encrypted store and never pass through tool arguments)

    _executors: dict[str, Any] = {}
    _lock = threading.Lock()

    def _store():
        # honor SEATUNNEL_DC_PRESETS_PATH at CALL time (the module-level
        # default is baked at import, which breaks test/app isolation)
        import os
        from .data_comparison import presets as _p
        path = os.environ.get("SEATUNNEL_DC_PRESETS_PATH") or _p._DEFAULT_PATH
        return _p.ConnectionPresetsStore(path)

    def _executor_for(name: str):
        """(executor, error_message) — cached per connection name."""
        key = (name or "").strip()
        if not key:
            return None, "connection 不能为空 / connection name required"
        with _lock:
            if key in _executors:
                return _executors[key], ""
        try:
            preset = _store().get_by_name(key)
        except Exception as exc:  # noqa: BLE001
            return None, f"读取连接预设失败 / preset store error: {exc}"
        if not preset:
            try:
                names = [p.get("name", "") for p in _store().list()]
            except Exception:  # noqa: BLE001
                names = []
            hint = f"；已保存: {', '.join(n for n in names if n)}" if names else ""
            return None, f"未找到连接 '{key}' / connection not found{hint}"
        from .text2sql.executor.base import DatabaseConfig, create_executor
        try:
            cfg = DatabaseConfig(
                ds_type=str(preset.get("ds_type") or ""),
                host=str(preset.get("host") or ""),
                port=int(preset.get("port") or 0),
                database=str(preset.get("database") or ""),
                username=str(preset.get("username") or "") or None,
                password=str(preset.get("password") or "") or None,
            )
            executor = create_executor(cfg)
            ok, info = executor.test_connection()
            if not ok:
                return None, f"连接失败 / connection failed: {info}"
        except Exception as exc:  # noqa: BLE001
            return None, f"连接失败 / connection failed: {exc}"
        with _lock:
            _executors[key] = executor
        return executor, ""

    def list_saved_connections() -> str:
        """列出已保存的数据库连接（在 Web 界面 /settings 或数据比对页维护）。
        后续工具用返回的连接名引用数据库，凭据不经过模型上下文。"""
        try:
            presets = _store().list()
        except Exception as exc:  # noqa: BLE001
            return f"读取连接预设失败 / preset store error: {exc}"
        if not presets:
            return ("暂无已保存连接——在 Web 界面 /settings 的“数据库连接”里添加。"
                    " / No saved connections; add one on the /settings page.")
        lines = ["| name | type | host | database |", "|---|---|---|---|"]
        for p in presets:
            lines.append(f"| {p.get('name', '')} | {p.get('ds_type', '')} "
                         f"| {p.get('host', '')}:{p.get('port', '')} "
                         f"| {p.get('database', '')} |")
        return "\n".join(lines)

    def list_tables(connection: str, keyword: str = "") -> str:
        """列出连接中的表名；keyword 可选（不区分大小写的子串过滤）。"""
        executor, err = _executor_for(connection)
        if err:
            return err
        try:
            names = executor.show_tables()
        except Exception as exc:  # noqa: BLE001
            return f"查询失败 / query failed: {exc}"
        kw = (keyword or "").strip().lower()
        if kw:
            names = [n for n in names if kw in n.lower()]
        if not names:
            return "（无匹配的表 / no matching tables）"
        return "\n".join(f"- {n}" for n in names[:200])

    def table_schema(connection: str, table: str) -> str:
        """查看一张表的结构：列名/类型/注释与分区列。"""
        executor, err = _executor_for(connection)
        if err:
            return err
        if not _SIMPLE_TABLE_RE.match((table or "").strip()):
            return f"非法表名 / invalid table name: {table!r}"
        try:
            schema = executor.describe_table(table.strip())
        except Exception as exc:  # noqa: BLE001
            return f"查询失败 / query failed: {exc}"
        lines = [f"**{schema.full_name}**"
                 + (f" — {schema.comment}" if schema.comment else ""),
                 "", "| column | type | comment |", "|---|---|---|"]
        for c in schema.columns:
            lines.append(f"| {c.name} | {c.dtype} | {c.comment} |")
        if schema.partition_columns:
            parts = ", ".join(f"{c.name} ({c.dtype})"
                              for c in schema.partition_columns)
            lines += ["", f"partition columns: {parts}"]
        return "\n".join(lines)

    def run_query(connection: str, sql: str, max_rows: int = 100) -> str:
        """在已保存连接上执行**只读**查询（仅允许单条 SELECT/WITH；多语句、
        写操作一律拒绝），返回 Markdown 结果表。max_rows 上限 500。"""
        from .data_skew.consistency import extract_single_select

        executor, err = _executor_for(connection)
        if err:
            return err
        query = extract_single_select(sql or "")
        if query is None:
            return ("仅允许单条 SELECT/WITH 只读查询 / only a single read-only "
                    "SELECT/WITH statement is allowed")
        n = max(1, min(int(max_rows or 100), MAX_QUERY_ROWS))
        try:
            res = executor.run(query, max_rows=n)
        except Exception as exc:  # noqa: BLE001
            return f"查询失败 / query failed: {exc}"
        if not res.rows:
            return "（0 行 / 0 rows）"
        table = _fmt_rows(res.columns, res.rows)
        return f"{table}\n\n({len(res.rows)} rows, {res.elapsed_ms} ms)"

    def compare_row_count(connection_a: str, connection_b: str, table_a: str,
                          table_b: str = "", where: str = "") -> str:
        """跨连接比对两张表的行数（table_b 留空则与 table_a 同名；where
        可选，同时作用于两侧）。返回两侧行数与差值。"""
        tb = (table_b or table_a or "").strip()
        for t in (table_a, tb):
            if not _SIMPLE_TABLE_RE.match((t or "").strip()):
                return f"非法表名 / invalid table name: {t!r}"
        if re.search(r"[;]", where or ""):
            return "where 条件不能包含分号 / ';' not allowed in where"
        counts = []
        for conn, table in ((connection_a, table_a.strip()), (connection_b, tb)):
            executor, err = _executor_for(conn)
            if err:
                return err
            q = f"SELECT COUNT(*) FROM {table}"
            if (where or "").strip():
                q += f" WHERE {where.strip()}"
            try:
                res = executor.run(q, max_rows=1)
            except Exception as exc:  # noqa: BLE001
                return f"[{conn}] 查询失败 / query failed: {exc}"
            counts.append(int(res.rows[0][0] or 0))
        a, b = counts
        mark = "✅" if a == b else "⛔"
        return (f"{mark} {connection_a}.{table_a}: {a} rows · "
                f"{connection_b}.{tb}: {b} rows · diff: {b - a:+d}")

    def compare_schema(connection_a: str, connection_b: str, table_a: str,
                       table_b: str = "") -> str:
        """跨连接比对两张表的结构：仅一侧存在的列、同名列类型差异。"""
        tb = (table_b or table_a or "").strip()
        for t in (table_a, tb):
            if not _SIMPLE_TABLE_RE.match((t or "").strip()):
                return f"非法表名 / invalid table name: {t!r}"
        schemas = []
        for conn, table in ((connection_a, table_a.strip()), (connection_b, tb)):
            executor, err = _executor_for(conn)
            if err:
                return err
            try:
                schemas.append(executor.describe_table(table))
            except Exception as exc:  # noqa: BLE001
                return f"[{conn}] 查询失败 / query failed: {exc}"
        sa, sb = schemas
        cols_a = {c.name.lower(): c for c in sa.columns}
        cols_b = {c.name.lower(): c for c in sb.columns}
        only_a = [c.name for c in sa.columns if c.name.lower() not in cols_b]
        only_b = [c.name for c in sb.columns if c.name.lower() not in cols_a]
        type_diff = [
            f"{name}: {cols_a[name].dtype} vs {cols_b[name].dtype}"
            for name in (c.name.lower() for c in sa.columns)
            if name in cols_b
            and cols_a[name].dtype.lower() != cols_b[name].dtype.lower()
        ]
        if not (only_a or only_b or type_diff):
            return (f"✅ 结构一致（{len(sa.columns)} 列）/ schemas match "
                    f"({len(sa.columns)} columns)")
        lines = ["⛔ 结构存在差异 / schemas differ:"]
        if only_a:
            lines.append(f"- 仅 {connection_a}.{table_a}: {', '.join(only_a)}")
        if only_b:
            lines.append(f"- 仅 {connection_b}.{tb}: {', '.join(only_b)}")
        if type_diff:
            lines.append("- 类型差异 / type differences: " + "; ".join(type_diff))
        return "\n".join(lines)

    tools.update(
        list_saved_connections=list_saved_connections,
        list_tables=list_tables,
        table_schema=table_schema,
        run_query=run_query,
        compare_row_count=compare_row_count,
        compare_schema=compare_schema,
    )

    # ── lineage tools (only when a graph source is configured) ──────────
    if sql_dir or seatunnel_dir or use_hive:
        from .data_lineage.mcp_server import build_tool_functions as _lin_tools
        tools.update(_lin_tools(
            sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
            meta_table=meta_table, partition=partition,
            sql_dialect=sql_dialect,
        ))

    return tools


def create_mcp_server(
    default_lang: str = "zh",
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    sql_dialect: str = "hive",
):
    """FastMCP server (stdio) wrapping the whole toolbox."""
    from .mcp_compat import fastmcp_class

    server = fastmcp_class()("seatunnel-agent", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        default_lang=default_lang, sql_dir=sql_dir,
        seatunnel_dir=seatunnel_dir, use_hive=use_hive,
        meta_table=meta_table, partition=partition, sql_dialect=sql_dialect,
    )
    for fn in functions.values():
        server.tool()(fn)
    return server
