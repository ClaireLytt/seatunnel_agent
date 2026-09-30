# -*- coding: utf-8 -*-
"""MCP server exposing the data-skew static analyzer over stdio.

Start with ``seatunnel-agent skew-mcp`` and register it in an MCP client
(Claude Desktop / Claude Code / Cline).  Mirrors the lineage MCP server's
shape: the tool callables are plain functions built by
:func:`build_tool_functions`, usable and testable without the ``mcp``
package; :func:`create_mcp_server` only wires them into FastMCP.

The static scan is deterministic, executes nothing and needs no LLM or
database, which makes it a safe tool to hand to an external agent.
"""

from __future__ import annotations

from typing import Callable

from .detector import DIALECTS, _DIALECT_ALIASES
from .history import default_history

_INSTRUCTIONS = (
    "SQL 数据倾斜静态分析：识别 COUNT(DISTINCT) 单点、NULL 关联键、全局排序/去重、"
    "JOIN 键函数、动态分区未打散等倾斜写法，输出严重度分级的中文/英文 Markdown 报告"
    "与引擎参数建议。支持 Spark SQL / MaxCompute SQL / Hive SQL。skew_check 系列为"
    "纯静态规则，不执行 SQL、不调用 LLM；skew_split_key 系列会按 .env 中的数据源"
    "配置连库执行只读的分布探查（COUNT/GROUP BY），用于 SeaTunnel 分片键体检；"
    "skew_split_key_apply 额外返回写入推荐分片键后的完整配置文本（不落盘）。"
    "skew_runtime 系列从 Spark event log / History Server 的任务指标定位"
    "拖尾 stage（运行时倾斜实锤），并映射回对应 SQL。"
)

# Engines whose executor supports the split-key probe queries
_SPLITKEY_DS = ("hive", "sparksql", "mysql", "postgresql", "sqlite",
                "clickhouse", "doris")


def build_tool_functions(
    default_dialect: str = "spark",
    default_lang: str = "zh",
    include_db: bool = True,
) -> dict[str, Callable[..., str]]:
    """Skew tool callables keyed by name.

    *include_db=False* returns only the pure-static tools — the unified
    toolbox composes those and provides its own saved-connection variant
    of the split-key check; the .env-based one here serves the standalone
    ``skew-mcp`` server."""
    history = default_history()

    def skew_check(sql: str, dialect: str = "", lang: str = "") -> str:
        """静态分析 SQL 的数据倾斜风险，返回 Markdown 报告（严重度分级 + 优化建议
        + 引擎参数）。dialect: spark / maxcompute / hive；lang: zh / en。"""
        from .agent import static_skew_report
        from .report import render_report

        sql = (sql or "").strip()
        if not sql:
            return "SQL 不能为空 / SQL must not be empty"
        # normalize_dialect() silently falls back to "spark", which would
        # hide a caller's typo — resolve aliases by hand and reject unknowns.
        raw = (dialect or default_dialect).strip().lower().replace(" ", "")
        d = _DIALECT_ALIASES.get(raw, raw)
        if d not in DIALECTS:
            return f"dialect 必须是 {', '.join(DIALECTS)} 之一"
        lg = (lang or default_lang).strip().lower()
        report = static_skew_report(sql, d, lg)
        history.log(sql, report, mode="static", source="mcp")
        return render_report(report, lg)

    def skew_check_file(path: str, dialect: str = "", lang: str = "") -> str:
        """静态分析一个 SQL 文件的数据倾斜风险（参数同 skew_check，path 为文件路径）。"""
        from pathlib import Path

        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"读取文件失败 / cannot read file: {exc}"
        return skew_check(text, dialect=dialect, lang=lang)

    def skew_runtime_eventlog(path: str, lang: str = "") -> str:
        """运行时倾斜诊断：解析 Spark event log（文件 / .gz / 滚动目录），按
        任务时长与 shuffle 读的 max/median 定位拖尾 stage，并把倾斜 stage
        映射回产生它的 SQL。离线分析，不连接任何集群。"""
        from .i18n import dsk
        from .runtime import (
            RuntimeSkewError,
            parse_eventlog,
            render_runtime_section,
        )

        lg = (lang or default_lang).strip().lower()
        try:
            stages, label = parse_eventlog((path or "").strip())
        except RuntimeSkewError as exc:
            return dsk(lg, exc.key).format(err=exc.arg)
        except OSError as exc:
            return f"读取文件失败 / cannot read file: {exc}"
        confirmed = sum(1 for s in stages if s.verdict() == "confirmed")
        suspect = sum(1 for s in stages if s.verdict() == "suspect")
        history.log_runtime(label, len(stages), confirmed, suspect,
                            source="mcp")
        return render_runtime_section(stages, lg, source_label=label)

    def skew_runtime_history(base_url: str, app_id: str, lang: str = "") -> str:
        """运行时倾斜诊断：调用 Spark History Server REST API
        （base_url 如 http://host:18080），按 taskSummary 分位数定位拖尾
        stage。只读 GET，每个应用最多约 21 次请求。"""
        from .i18n import dsk
        from .runtime import (
            RuntimeSkewError,
            analyze_history_server,
            render_runtime_section,
        )

        lg = (lang or default_lang).strip().lower()
        try:
            stages, label = analyze_history_server(base_url, app_id)
        except RuntimeSkewError as exc:
            return dsk(lg, exc.key).format(err=exc.arg)
        confirmed = sum(1 for s in stages if s.verdict() == "confirmed")
        suspect = sum(1 for s in stages if s.verdict() == "suspect")
        history.log_runtime(label, len(stages), confirmed, suspect,
                            source="mcp")
        return render_runtime_section(stages, lg, source_label=label)

    if not include_db:
        return {"skew_check": skew_check, "skew_check_file": skew_check_file,
                "skew_runtime_eventlog": skew_runtime_eventlog,
                "skew_runtime_history": skew_runtime_history}

    def skew_split_key(conf: str, ds_type: str = "mysql",
                       sample_pct: int = 0, lang: str = "") -> str:
        """SeaTunnel 分片键体检：解析作业配置（HOCON）中 JDBC source 的
        partition_column，按 .env 中该 ds_type 的连接配置连库实测其分布
        （NDV / NULL 占比 / top-1 占比，只读查询），并实测候选列给出推荐。
        ds_type: hive / sparksql / mysql / postgresql / sqlite / clickhouse / doris。"""
        from ..text2sql.executor.base import config_from_env, create_executor
        from .probe import effective_sample_pct
        from .splitkey import (
            SplitKeyError,
            render_splitkey_multi,
            run_split_key_multi,
            splitkey_metrics,
        )

        conf = (conf or "").strip()
        if not conf:
            return "配置不能为空 / config must not be empty"
        ds = (ds_type or "mysql").strip().lower()
        if ds not in _SPLITKEY_DS:
            return f"ds_type 必须是 {', '.join(_SPLITKEY_DS)} 之一"
        cfg = config_from_env(ds)
        if cfg is None:
            return (f"未在 .env 中找到 {ds} 的连接配置 / "
                    f"no {ds} connection configured in .env")
        lg = (lang or default_lang).strip().lower()
        pct = effective_sample_pct(ds, int(sample_pct or 0))
        try:
            executor = create_executor(cfg)
            results, total = run_split_key_multi(
                executor, conf, ds_type=ds, sample_pct=pct)
        except SplitKeyError as exc:
            from .i18n import dsk
            return dsk(lg, exc.key).format(err=exc.arg)
        except Exception as exc:  # noqa: BLE001 — surface to the caller
            return f"体检失败 / split-key check failed: {exc}"
        previous_by_table = {spec.table: prev for spec, _, _ in results
                             if (prev := history.last_splitkey(spec.table))}
        for spec, configured, candidates in results:
            history.log_splitkey(
                spec.table, spec.partition_column,
                configured.verdict(spec.tasks) if configured else "none",
                candidates=len(candidates), source="mcp",
                **splitkey_metrics(configured))
        return render_splitkey_multi(results, lg, sample_pct=pct, total=total,
                                     previous_by_table=previous_by_table)

    def skew_split_key_file(path: str, ds_type: str = "mysql",
                            sample_pct: int = 0, lang: str = "") -> str:
        """SeaTunnel 分片键体检（参数同 skew_split_key，path 为配置文件路径）。"""
        from pathlib import Path

        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"读取文件失败 / cannot read file: {exc}"
        return skew_split_key(text, ds_type=ds_type,
                              sample_pct=sample_pct, lang=lang)

    def skew_split_key_apply(conf: str, ds_type: str = "mysql",
                             sample_pct: int = 0, lang: str = "") -> str:
        """在 skew_split_key 实测的基础上，把推荐分片键写入配置并返回修改后的
        完整配置文本（不落盘，由调用方保存）。仅支持单 source 配置；无需修改时
        返回说明。参数同 skew_split_key。"""
        from ..text2sql.executor.base import config_from_env, create_executor
        from .i18n import dsk
        from .probe import effective_sample_pct
        from .splitkey import (
            SplitKeyError,
            apply_split_key,
            pick_best_key,
            run_split_key_multi,
        )

        conf = (conf or "").strip()
        if not conf:
            return "配置不能为空 / config must not be empty"
        ds = (ds_type or "mysql").strip().lower()
        if ds not in _SPLITKEY_DS:
            return f"ds_type 必须是 {', '.join(_SPLITKEY_DS)} 之一"
        cfg = config_from_env(ds)
        if cfg is None:
            return (f"未在 .env 中找到 {ds} 的连接配置 / "
                    f"no {ds} connection configured in .env")
        lg = (lang or default_lang).strip().lower()
        pct = effective_sample_pct(ds, int(sample_pct or 0))
        try:
            executor = create_executor(cfg)
            results, total = run_split_key_multi(
                executor, conf, ds_type=ds, sample_pct=pct)
        except SplitKeyError as exc:
            return dsk(lg, exc.key).format(err=exc.arg)
        except Exception as exc:  # noqa: BLE001 — surface to the caller
            return f"体检失败 / split-key check failed: {exc}"
        if total > 1:
            return dsk(lg, "spk_apply_multi").format(n=total)
        spec, configured, candidates = results[0]
        best = pick_best_key(spec, configured, candidates)
        if best is None or best.column == spec.partition_column:
            return dsk(lg, "spk_apply_none")
        try:
            patched = apply_split_key(
                conf, spec, best.column,
                partition_num=max(spec.partition_num, spec.tasks))
        except SplitKeyError as exc:
            return dsk(lg, exc.key).format(err=exc.arg)
        # a HOCON comment header keeps the return directly saveable
        note = (f"# split key: {spec.split_option} -> \"{best.column}\" "
                f"(was \"{spec.partition_column or '(none)'}\", measured)")
        return f"{note}\n{patched}"

    return {
        "skew_check": skew_check,
        "skew_check_file": skew_check_file,
        "skew_runtime_eventlog": skew_runtime_eventlog,
        "skew_runtime_history": skew_runtime_history,
        "skew_split_key": skew_split_key,
        "skew_split_key_file": skew_split_key_file,
        "skew_split_key_apply": skew_split_key_apply,
    }


def create_mcp_server(default_dialect: str = "spark", default_lang: str = "zh"):
    """FastMCP server (stdio) wrapping the skew tools."""
    from ..mcp_compat import fastmcp_class

    server = fastmcp_class()("seatunnel-dataskew", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        default_dialect=default_dialect, default_lang=default_lang)
    for fn in functions.values():
        server.tool()(fn)
    return server
