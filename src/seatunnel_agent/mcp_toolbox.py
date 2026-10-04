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

import functools
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

MAX_QUERY_ROWS = 500

# engines whose SQL accepts a trailing LIMIT on a wrapped subquery — for
# the rest, run_query falls back to the fetch-side cap only
_LIMIT_DS = frozenset({"hive", "sparksql", "mysql", "postgresql", "sqlite",
                       "clickhouse", "doris", "starrocks"})

# tool-call audit trail (an AI client is executing these against real
# databases): logs/mcp_toolbox.jsonl, best-effort, 10 MB rotation
_AUDIT_ENV = "SEATUNNEL_MCP_AUDIT_PATH"
_AUDIT_MAX_BYTES = 10 * 1024 * 1024
_audit_lock = threading.Lock()


def _audit_file() -> Path:
    override = os.environ.get(_AUDIT_ENV)
    return Path(override) if override else Path("logs") / "mcp_toolbox.jsonl"


def _write_audit(record: dict) -> None:
    try:
        path = _audit_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _audit_lock:
            if path.exists() and path.stat().st_size > _AUDIT_MAX_BYTES:
                path.replace(path.with_suffix(".jsonl.1"))
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # auditing must never break a tool call


def _audited(name: str, fn: Callable[..., str]) -> Callable[..., str]:
    """Wrap a tool: one audit line per call, exceptions become error text.

    functools.wraps keeps __doc__ and __wrapped__, so FastMCP still sees
    the real signature and docstring when building the tool schema."""
    from datetime import datetime, timezone

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        t0 = time.time()
        ok = True
        try:
            out = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — errors are strings, always
            ok = False
            out = f"内部错误 / internal error: {type(exc).__name__}: {exc}"
        summary = ", ".join(
            [*(repr(a)[:120] for a in args),
             *(f"{k}={repr(v)[:120]}" for k, v in kwargs.items())])
        _write_audit({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": name,
            "ok": ok and not str(out).startswith(("内部错误", "查询失败", "连接失败")),
            "args": summary[:400],
            "chars": len(str(out)),
            "elapsed_ms": int((time.time() - t0) * 1000),
        })
        return out

    return wrapper

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
    connections: list[str] | None = None,
    include_db: bool = True,
) -> dict[str, Callable[..., str]]:
    """All toolbox callables keyed by tool name.

    Lineage tools are included only when a lineage source (*sql_dir*,
    *seatunnel_dir* or *use_hive*) is configured — they need a graph.
    *connections* is an allowlist of saved-connection NAMES the database
    tools may use (None = all); *include_db=False* drops the database
    tools entirely (a pure-static server with zero DB attack surface).
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

    if not include_db:
        return {name: _audited(name, fn) for name, fn in tools.items()}

    # ── database tools over NAMED saved connections ─────────────────────
    # (shared store with the Settings / Data Comparison pages; passwords
    # stay in the encrypted store and never pass through tool arguments)

    _allow = {n.strip() for n in (connections or []) if n.strip()} or None
    _executors: dict[str, Any] = {}
    _lock = threading.Lock()
    _pool: dict[str, Any] = {}

    def _invalidate(name: str) -> None:
        """Drop a cached executor so the next call reconnects — a database
        restart must not brick the long-running server."""
        with _lock:
            _executors.pop((name or "").strip(), None)

    def _db(name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a DB call with a hard timeout (a hung query must not block
        the MCP client forever). The underlying query may keep running in
        its thread — the tool call itself always returns."""
        import concurrent.futures

        timeout = float(os.environ.get("SEATUNNEL_MCP_QUERY_TIMEOUT", "60"))
        with _lock:
            pool = _pool.get("pool")
            if pool is None:
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
                _pool["pool"] = pool
        fut = pool.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            _invalidate(name)
            raise TimeoutError(
                f"查询超时（{timeout:.0f}s，连接已重置）/ query timed out "
                f"after {timeout:.0f}s; connection reset") from None

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
        if _allow is not None and key not in _allow:
            return None, (f"连接 '{key}' 不在服务启动时的白名单内 / connection "
                          f"not in the server's allowlist: {', '.join(sorted(_allow))}")
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
        if _allow is not None:
            presets = [p for p in presets if p.get("name") in _allow]
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
            names = _db(connection, executor.show_tables)
        except Exception as exc:  # noqa: BLE001
            _invalidate(connection)
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
            schema = _db(connection, executor.describe_table, table.strip())
        except Exception as exc:  # noqa: BLE001
            _invalidate(connection)
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
        写操作一律拒绝），返回 Markdown 结果表。max_rows 上限 500，且在
        支持 LIMIT 的引擎上注入引擎侧 LIMIT（大表不做全量计算）。"""
        from .data_skew.consistency import extract_single_select

        executor, err = _executor_for(connection)
        if err:
            return err
        query = extract_single_select(sql or "")
        if query is None:
            return ("仅允许单条 SELECT/WITH 只读查询 / only a single read-only "
                    "SELECT/WITH statement is allowed")
        n = max(1, min(int(max_rows or 100), MAX_QUERY_ROWS))
        # engine-side cap: the fetch cap alone still lets the engine
        # compute the full result (a LIMIT-less SELECT on a big Hive
        # table would full-scan)
        if executor.config.ds_type in _LIMIT_DS:
            query = f"SELECT * FROM (\n{query}\n) mcp_q LIMIT {n}"
        try:
            res = _db(connection, executor.run, query, max_rows=n)
        except Exception as exc:  # noqa: BLE001
            _invalidate(connection)
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
                res = _db(conn, executor.run, q, max_rows=1)
            except Exception as exc:  # noqa: BLE001
                _invalidate(conn)
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
                schemas.append(_db(conn, executor.describe_table, table))
            except Exception as exc:  # noqa: BLE001
                _invalidate(conn)
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

    def skew_verify(connection: str, sql: str, dialect: str = "spark",
                    sample_pct: int = 10, lang: str = "") -> str:
        """连库**实测验证**数据倾斜：解析 SQL 里的 JOIN/GROUP BY/COUNT(DISTINCT)/
        窗口分区键，在已保存连接上并行探查真实键值分布（只读 GROUP BY 探针，
        支持 TABLESAMPLE 采样），返回确认/疑似判定、热点值、引擎参数与按实测
        值生成的改写模板。先用 skew_check 做静态扫描，再用本工具实测确认。"""
        from .data_skew.detector import normalize_dialect
        from .data_skew.probe import (
            effective_sample_pct, extract_probe_targets, render_probe_section,
            run_probes)

        executor, err = _executor_for(connection)
        if err:
            return err
        if not (sql or "").strip():
            return "SQL 不能为空 / SQL must not be empty"
        targets = extract_probe_targets(sql)
        ds = executor.config.ds_type
        pct = effective_sample_pct(ds, int(sample_pct or 0))
        try:
            results = _db(connection, run_probes, executor, targets,
                          ds_type=ds, sample_pct=pct)
        except Exception as exc:  # noqa: BLE001
            _invalidate(connection)
            return f"探查失败 / probing failed: {exc}"
        from .data_skew.history import default_history
        default_history().log_verify(
            sql, targets=len(targets),
            confirmed=sum(1 for r in results if r.verdict == "confirmed"),
            source="mcp")
        return render_probe_section(results, _lang(lang),
                                    dialect=normalize_dialect(dialect),
                                    sample_pct=pct)

    def compare_query_results(connection: str, original_sql: str,
                              optimized_sql: str, lang: str = "") -> str:
        """一致性实测：在同一连接上运行两版 SQL（各自仅允许单条 SELECT/WITH）
        并比对——行数一致性、小结果集逐行多重集比对、大结果集逐列聚合指纹。
        用于验证改写/迁移后的 SQL 与原 SQL 结果等价。"""
        from .data_skew.consistency import (check_consistency,
                                            render_consistency_section)

        executor, err = _executor_for(connection)
        if err:
            return err
        try:
            res = _db(connection, check_consistency, executor,
                      original_sql or "", optimized_sql or "")
        except TimeoutError as exc:
            _invalidate(connection)
            return str(exc)
        return render_consistency_section(res, _lang(lang))

    def compare_checksum(connection_a: str, connection_b: str, table_a: str,
                         table_b: str = "", where: str = "") -> str:
        """跨连接比对两张表的分段校验和（同名列取交集，逐段哈希）：行数/结构
        都一致后仍怀疑内容差异时用它，比逐行拉数便宜得多。where 可选，同时
        作用于两侧，禁分号。"""
        from .data_comparison.comparator import (build_checksum_sql,
                                                 compare_checksums)

        tb = (table_b or table_a or "").strip()
        for t in (table_a, tb):
            if not _SIMPLE_TABLE_RE.match((t or "").strip()):
                return f"非法表名 / invalid table name: {t!r}"
        if re.search(r"[;]", where or ""):
            return "where 条件不能包含分号 / ';' not allowed in where"
        sides = []
        for conn, table in ((connection_a, table_a.strip()), (connection_b, tb)):
            executor, err = _executor_for(conn)
            if err:
                return err
            try:
                schema = _db(conn, executor.describe_table, table)
            except Exception as exc:  # noqa: BLE001
                _invalidate(conn)
                return f"[{conn}] 查询失败 / query failed: {exc}"
            sides.append((executor, table, schema))
        (ex_a, ta, sa), (ex_b, tbx, sb) = sides
        names_b = {c.name.lower() for c in sb.columns}
        cols = [c.name for c in sa.columns if c.name.lower() in names_b]
        if not cols:
            return "两表无同名列，无法计算校验和 / no shared columns"
        rows = []
        for conn_name, ex, table in ((connection_a, ex_a, ta),
                                     (connection_b, ex_b, tbx)):
            q = build_checksum_sql(table, cols, ds_type=ex.config.ds_type,
                                   where=(where or "").strip())
            try:
                rows.append(_db(conn_name, ex.run, q, max_rows=64).rows)
            except Exception as exc:  # noqa: BLE001
                _invalidate(conn_name)
                return f"[{table}] 校验和查询失败 / checksum query failed: {exc}"
        result = compare_checksums(ta, tbx, rows[0], rows[1])
        if not result.mismatch_count:
            return (f"✅ 校验和一致：{result.match_count} 段全部匹配"
                    f"（{len(cols)} 列参与）")
        bad = [f"seg {i.segment}: {i.checksum_a[:24]} vs {i.checksum_b[:24]}"
               for i in result.items if not i.match][:10]
        return (f"⛔ 校验和不一致：{result.mismatch_count} 段不匹配 / "
                f"{result.match_count} 段匹配（{len(cols)} 列参与）\n- "
                + "\n- ".join(bad))

    tools.update(
        list_saved_connections=list_saved_connections,
        list_tables=list_tables,
        table_schema=table_schema,
        run_query=run_query,
        compare_row_count=compare_row_count,
        compare_schema=compare_schema,
        skew_verify=skew_verify,
        compare_query_results=compare_query_results,
        compare_checksum=compare_checksum,
    )

    # ── lineage tools (only when a graph source is configured) ──────────
    if sql_dir or seatunnel_dir or use_hive:
        from .data_lineage.mcp_server import build_tool_functions as _lin_tools
        tools.update(_lin_tools(
            sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
            meta_table=meta_table, partition=partition,
            sql_dialect=sql_dialect,
        ))

        _dict_state: dict[str, Any] = {"graph": None}

        def data_dictionary(lang: str = "") -> str:
            """从血缘图生成数据字典（分层排序的表清单：来源/去向/字段血缘），
            不连接数据库。"""
            from .data_lineage.dictionary import (build_dictionary,
                                                  render_dictionary_markdown)
            from .data_lineage.loaders import build_graph

            if _dict_state["graph"] is None:
                _dict_state["graph"], _ = build_graph(
                    sql_dir=sql_dir, seatunnel_dir=seatunnel_dir,
                    use_hive=use_hive, meta_table=meta_table,
                    partition=partition, sql_dialect=sql_dialect)
            entries = build_dictionary(_dict_state["graph"])
            return render_dictionary_markdown(entries, _lang(lang))

        tools["data_dictionary"] = data_dictionary

    # every tool gets the audit wrapper (one jsonl line per call; an
    # exception becomes error text instead of a protocol-level failure)
    return {name: _audited(name, fn) for name, fn in tools.items()}


def create_mcp_server(
    default_lang: str = "zh",
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    sql_dialect: str = "hive",
    connections: list[str] | None = None,
    include_db: bool = True,
):
    """FastMCP server (stdio) wrapping the whole toolbox."""
    from . import __version__
    from .mcp_compat import fastmcp_class

    cls = fastmcp_class()
    try:
        server = cls("seatunnel-agent", instructions=_INSTRUCTIONS,
                     version=__version__)
    except TypeError:  # older SDKs without a version kwarg
        server = cls("seatunnel-agent", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        default_lang=default_lang, sql_dir=sql_dir,
        seatunnel_dir=seatunnel_dir, use_hive=use_hive,
        meta_table=meta_table, partition=partition, sql_dialect=sql_dialect,
        connections=connections, include_db=include_db,
    )

    # every tool is read-only; the pure-static ones are idempotent too
    # (db-backed answers can change between calls as data changes)
    static_names = {"sql_review", "sql_transpile", "skew_check",
                    "skew_check_file", "impact_diff", "migrate_to_seatunnel"}
    annotations_cls = None
    try:
        from mcp.types import ToolAnnotations as annotations_cls
    except ImportError:
        pass
    for name, fn in functions.items():
        if annotations_cls is not None:
            try:
                server.tool(annotations=annotations_cls(
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=name in static_names,
                ))(fn)
                continue
            except TypeError:
                pass  # SDK without the annotations kwarg
        server.tool()(fn)

    _register_prompts(server)
    _register_resources(server, functions)
    return server


def _register_resources(server, functions: dict[str, Callable[..., str]]) -> None:
    """Static catalogs as MCP resources — browsable without spending a tool
    call (best-effort: skipped on SDKs without resource support)."""
    if not hasattr(server, "resource"):
        return

    def skew_rule_catalog() -> str:
        """数据倾斜静态规则目录（DS001–DS013）。"""
        from .data_skew.detector import RULE_TEXTS

        lines = ["# Data Skew rules", ""]
        for key in sorted(RULE_TEXTS):
            desc = RULE_TEXTS[key].get("zh", {}).get("desc", "")
            lines.append(f"- **{key}**: {desc}")
        return "\n".join(lines)

    def review_rule_catalog() -> str:
        """SQL 审查规则类别目录。"""
        from .sql_review.report import CHECK_CATALOG

        lines = ["# SQL Review categories", ""]
        for key, label in CHECK_CATALOG.items():
            lines.append(f"- **{key}**: {label}")
        return "\n".join(lines)

    def dialect_catalog() -> str:
        """各工具支持的方言清单。"""
        from .data_skew.detector import DIALECTS as skew_d
        from .sql_review.linter import DIALECTS as review_d
        from .sql_transpile import DIALECTS as transpile_d

        return ("# Supported dialects\n\n"
                f"- sql_review: {', '.join(review_d)}\n"
                f"- sql_transpile: {', '.join(transpile_d)}\n"
                f"- skew_check / skew_verify: {', '.join(skew_d)}\n")

    resources = [
        ("seatunnel://rules/data-skew", skew_rule_catalog),
        ("seatunnel://rules/sql-review", review_rule_catalog),
        ("seatunnel://dialects", dialect_catalog),
    ]
    if "list_saved_connections" in functions:
        def saved_connections() -> str:
            """已保存的数据库连接（名称/类型/host/库，不含凭据）。"""
            return functions["list_saved_connections"]()

        resources.append(("seatunnel://connections", saved_connections))
    for uri, fn in resources:
        try:
            server.resource(uri)(fn)
        except Exception:  # noqa: BLE001 — resources are optional polish
            return


def _register_prompts(server) -> None:
    """Canned multi-tool workflows as MCP prompts (best-effort: skipped on
    SDKs without prompt support)."""
    if not hasattr(server, "prompt"):
        return

    def skew_tuning_workflow(sql: str, connection: str = "") -> str:
        """数据倾斜调优全流程：静态扫描 → 实测验证 → 改写 → 一致性验收。"""
        conn = connection.strip() or "<用 list_saved_connections 选一个>"
        return (
            "请按以下流程对这段 SQL 做数据倾斜调优：\n"
            f"1. 用 skew_check 做静态扫描（原文如下）。\n"
            f"2. 用 skew_verify(connection={conn!r}) 实测验证，拿到确认倾斜的键、"
            "热点值与改写模板。\n"
            "3. 基于实测热点值改写 SQL（优先热点隔离/两阶段聚合，参考返回的模板）。\n"
            f"4. 用 compare_query_results(connection={conn!r}) 验证改写与原 SQL "
            "结果等价，不等价则修正后重验。\n"
            "5. 汇总：确认的倾斜点、改写后 SQL、建议引擎参数。\n\n"
            f"```sql\n{sql.strip()}\n```"
        )

    def migration_acceptance_workflow(connection_a: str, connection_b: str,
                                      table: str) -> str:
        """迁移验收三级比对：结构 → 行数 → 校验和。"""
        return (
            f"请对迁移表 {table} 做验收比对（源连接 {connection_a!r}，目标连接 "
            f"{connection_b!r}），按代价从低到高逐级执行，任何一级不一致就停下"
            "分析原因：\n"
            f"1. compare_schema：结构差异（缺列/类型漂移）。\n"
            f"2. compare_row_count：行数差异（可加 where 缩小到分区）。\n"
            f"3. compare_checksum：分段校验和，定位内容差异所在的段。\n"
            "4. 需要看具体数据时用 run_query 抽样（只读）。\n"
            "最后输出验收结论：通过 / 不通过 + 差异清单。"
        )

    for fn in (skew_tuning_workflow, migration_acceptance_workflow):
        try:
            server.prompt()(fn)
        except Exception:  # noqa: BLE001 — prompts are optional polish
            return
